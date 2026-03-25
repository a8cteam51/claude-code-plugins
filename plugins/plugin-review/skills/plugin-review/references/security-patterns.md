# WordPress Plugin Security Review Guide

Use this guide during manual code review to assess findings from automated tools (PHPCS and grep scans) and identify issues they miss.

## Priority Reading Order

When a plugin has many files, read in this order:

1. **Main plugin file** (the one with `Plugin Name:` header) — understand what the plugin does
2. **Files flagged by PHPCS/grep** — assess whether findings are true positives
3. **AJAX handlers** — grep for `wp_ajax_` and `wp_ajax_nopriv_` action registrations
4. **REST API endpoints** — grep for `register_rest_route`
5. **Form handlers** — grep for `admin_post_` and `admin_init` hooks that process input
6. **File upload handlers** — grep for `wp_handle_upload`, `move_uploaded_file`, `$_FILES`
7. **Shortcode callbacks** — grep for `add_shortcode` (shortcodes run for all users)
8. **Widget render methods** — grep for `extends WP_Widget`

## Assessing Automated Findings

### Direct Superglobal Access ($_GET, $_POST, $_REQUEST)

**Not always a vulnerability.** Assess by checking:
- Is the value sanitized before use? Look for `sanitize_text_field()`, `absint()`, `intval()`, `esc_attr()`, etc.
- Is it used in a database query? Must go through `$wpdb->prepare()`.
- Is it echoed to the page? Must be escaped with `esc_html()`, `esc_attr()`, `wp_kses()`, etc.
- Is it only used in a comparison (e.g., `if ($_GET['action'] === 'delete')`)? Generally safe.

**True positive if:** Value flows to output, database, or file system without sanitization/escaping.

### eval(), exec(), system(), shell_exec(), passthru()

**Almost always a real concern.** Legitimate uses are extremely rare in WordPress plugins.
- `eval()` in a template engine might be intentional but is still risky
- `exec()`/`system()` for image processing (ImageMagick) happens but should use `escapeshellarg()`
- Flag as CRITICAL if user input can reach the argument

### base64_decode()

**Context-dependent.**
- Decoding a stored configuration value or image data: usually benign
- Decoding then `eval()`-ing the result: malicious/obfuscation
- Decoding external input: suspicious
- Multiple layers of encoding/decoding: red flag

### unserialize()

**HIGH risk with untrusted data.** PHP object injection can lead to RCE.
- Safe if deserializing data that was serialized by the same plugin internally
- Dangerous if deserializing user input, cookie values, or external API data
- WordPress provides `maybe_unserialize()` but it still calls `unserialize()` underneath

### file_get_contents() / file_put_contents()

**Check the path argument:**
- Hardcoded paths within the plugin directory: generally safe
- Paths constructed from user input: file inclusion/write vulnerability
- URLs as paths (remote file access): potential SSRF
- WordPress recommends `WP_Filesystem` API instead

### wp_remote_get() / wp_remote_post()

**Check the URL argument:**
- Hardcoded URLs to known APIs: safe
- URLs constructed from user input or options: potential SSRF
- Check if response is properly validated before use

### $wpdb->query() / Direct Database Queries

**Check for prepared statements:**
- `$wpdb->prepare()` used with placeholders: safe
- String concatenation with variables in SQL: SQL injection
- Even `$wpdb->insert()`, `$wpdb->update()`, `$wpdb->delete()` are safe (they prepare internally)

### Variable Function Calls ($func())

**Often false positives** from callbacks and WordPress hooks. True positive if:
- The function name comes from user input
- The function name comes from an unsanitized database value
- There's no whitelist of allowed function names

## WordPress-Specific Attack Surfaces

### Unauthenticated AJAX (wp_ajax_nopriv_)

Handlers registered with `wp_ajax_nopriv_` are accessible to **anyone without logging in**. Every such handler must:
- Verify a nonce (`check_ajax_referer()` or `wp_verify_nonce()`)
- Sanitize all input
- Escape all output
- Not perform privileged operations without additional auth checks

### Authenticated AJAX (wp_ajax_)

Accessible to any logged-in user, including subscribers. Must:
- Check capabilities with `current_user_can()` if the action is admin-only
- Verify a nonce
- Sanitize input, escape output

### REST API Routes

Check `register_rest_route()` calls for:
- `permission_callback` — must not be `__return_true` for sensitive operations
- Input validation via `validate_callback` and `sanitize_callback` on args
- Routes that accept file uploads

### Admin Post Handlers

Hooks like `admin_post_` and `admin_post_nopriv_` process form submissions:
- `admin_post_nopriv_*` is unauthenticated — same scrutiny as nopriv AJAX
- Must verify nonce and check capabilities

### Shortcodes

Shortcodes execute in post content for **any visitor**. Attributes come from the post author (typically trusted) but:
- Stored XSS if attribute values are echoed without escaping
- In multisite or sites with multiple authors, post authors may not be fully trusted

### Options and Settings

- `register_setting()` should include a `sanitize_callback`
- `update_option()` / `add_option()` with user-controlled keys = option injection
- Settings pages must verify nonces and capabilities

## JavaScript Security Patterns

The grep scan also checks `.js` files (excluding minified). Assess JS findings with the same true/false positive approach.

### innerHTML / outerHTML / document.write()

**HIGH risk if the content includes unsanitized data.** Check:
- Is the assigned value a hardcoded string or template literal with no variables? Safe.
- Does it include data from user input, URL parameters, or AJAX responses without escaping? XSS vulnerability.
- Is `DOMPurify.sanitize()` or equivalent used? Mitigated.

### jQuery .html(), .append(), .prepend(), .after(), .before()

**Context-dependent.** These insert raw HTML into the DOM.
- `.html('<div class="spinner"></div>')` — hardcoded string, safe.
- `.html(response.data)` where `response` comes from an AJAX call — XSS if the server doesn't escape the response, or if the AJAX endpoint is manipulable.
- `.append('<option>' + userInput + '</option>')` — XSS. Should use `.text()` for the content or build the element with jQuery's object syntax.
- `.html(template)` where `template` is built from plugin-internal data — usually safe, but verify the data source.

### eval() / new Function() in JavaScript

**Almost always a concern**, same as PHP `eval()`. Check:
- Is it parsing JSON? Should use `JSON.parse()` instead.
- Is it executing code from an AJAX response? Critical vulnerability.
- Is it part of a template engine or build tool artifact? Note but lower risk.

### Dynamic script creation

`createElement('script')` with a dynamic `src` — potential for loading malicious external scripts if the URL is user-controllable.

### localStorage / postMessage

**LOW risk, but worth noting:**
- `localStorage` — check what's being stored. Tokens, user data, or sensitive info in localStorage is accessible to any script on the same origin (XSS amplification).
- `postMessage` — check if `event.origin` is validated in the receiver. Missing origin checks allow cross-origin message injection.

## Red Flags Beyond Code Patterns

- **Obfuscated code**: Long strings of encoded characters, multiple base64 layers, `goto` obfuscation, `str_rot13`
- **External code loading**: `file_get_contents()` or `wp_remote_get()` fetching PHP that gets `eval()`-ed
- **Hidden admin users**: Code that creates admin accounts
- **Backdoor patterns**: Code that responds to specific URL parameters or cookies to execute arbitrary actions
- **Exfiltration**: Code that sends site data, credentials, or user info to external servers
- **License validation that phones home**: Excessive data collection during license checks
