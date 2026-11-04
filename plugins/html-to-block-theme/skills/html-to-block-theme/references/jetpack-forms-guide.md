# Jetpack Forms guide

Read this when the design has a contact or newsletter form and Jetpack is available: `jetpack/contact-form` is the mapping, and a one-field form covers a newsletter signup. `mapping-guide.md` still governs the blocks around the form.

Each passage says which Jetpack Forms version it was read or seen in. Those marked **(16.4)** come from a run on WordPress 7.1.4 with Jetpack 16.4: what a builder saw in the browser, in the editor or in Jetpack's source, reported in its hand-back and not checked a second time.

## On a local site

- **The `contact-form` module works offline; the `subscriptions` module does not.** It cannot activate without a WordPress.com connection, so do not map a newsletter signup to subscription blocks locally. Offline mode is a local-only shim, never committed (`project-template-guide.md` § Where each piece goes).
- **The Studio validator does not register Jetpack's form blocks.** A page with a form validates only its core blocks (`6/6`), skipping the form and every field. Validate in the site's own block editor (`agents/section-builder.md` § Validate). **(16.4)**
- **Never press submit in the original's pane** (`visual-refinement.md` § JS-driven sections). A submission that was not tried on the build is listed in the report as not checked.

## Markup

- **Field blocks are composed** (Jetpack Forms 16.x): a self-closing `<!-- wp:jetpack/field-email /-->` fails validation. The required shape is the field's wrapping `<div>` + `wp:jetpack/label` + `wp:jetpack/input` inner blocks.
- **Write the attributes the editor adds, or the page opens with unsaved changes.** When a form loads, Jetpack's editor adds defaults: on `jetpack/contact-form`, `jetpackCRM`, `salesforceData` and `mailpoet`; on `jetpack/field-name`, `fieldVariant: "name"`; on the submit `core/button`, `lock: {"move": false, "remove": true}`. A page written without them raises "Leave site?" when its tab closes and gets an autosave revision a minute after it opens. Copy them from what the editor writes (`wp.data.select( 'core/editor' ).getEditedPostContent()`) into the source, and the page opens clean. **(16.4)**
- **Any non-default `is-style-*` on `jetpack/contact-form` suppresses field labels** (16.0.1): apply `"className":"is-style-default is-style-<custom>"` together.
- **A form in a template part takes the page's title as its accessible name** unless `formTitle` is set: set it to what the form is. Read in Jetpack Forms 16.3.1.
- **The submit button is a `core/button`** with `"tagName":"button"` and `"type":"submit"`, inside the form, as the editor writes it. The form prints a button of its own, labelled "Submit", whenever its rendered content holds neither a `wp-block-button` nor a `wp-block-jetpack-button` class. A button block that validates and renders nothing is therefore replaced without a word: compare the button's label with the design's after the write. Read in Jetpack Forms 16.1.2.
- **A telephone field without the country selector is a plain input.** `jetpack/field-telephone` with `showCountrySelector: false` and an inner `jetpack/phone-input` renders `<input type="tel">` on the front end; the editor still wraps it differently. **(16.4)**

## Styling a form

- **Jetpack sizes the submit button from the first input.** Its view script copies that input's computed height and top padding into `--jetpack--contact-form--input-height` and `--jetpack--contact-form--input-padding-top` on the form's container, and `.wp-block-jetpack-contact-form :is(.wp-block-button) .wp-block-button__link` (0,3,0, printed after the theme's block stylesheets) applies them to the button. A form style that gives its inputs `padding-block: 0` (a design whose fields have a `min-height`) collapses the button's vertical padding, unless the style resets those two properties on `.wp-block-button`. **(16.4)**
- **One custom property colours the whole invalid state.** `--jetpack--contact-form--error-color` colours the control's border, the field's message and the summary. Redefine it on the form's style, rather than overriding Jetpack's `[aria-invalid]` rule (0,3,0). **(16.4)**
- **The confirmation is outside the form's block.** `.contact-form-submission` is a sibling of the `<form>`, inside `.jetpack-contact-form-container`, so the block's wrapper and its `is-style-*` class do not reach it. A form style reaches it with `.jetpack-contact-form-container:has( .wp-block-jetpack-contact-form.is-style-x ) > .contact-form-submission.submission-success`; Dart Sass compiles `:has( & )` inside the nested rule. **(16.4)**

## Accessibility

- **Jetpack prints no `autocomplete` attribute on any field.** A `render_block_jetpack/contact-form` filter with `WP_HTML_Tag_Processor` adds `name`, `email` and `tel` by the field's wrapper class (`wp-block-jetpack-field-name`, `-email`, `-telephone`), without touching the form's signed content. **(16.4)**
