# WooCommerce guide

Read this when the blueprint has a store: WooCommerce is installed, or one of its blocks is in a view, a template or a part. `mapping-guide.md` still governs every block that is not WooCommerce's. This guide is what WooCommerce changes.

Each passage says what it was checked with. Passages without a version were checked with WooCommerce 11.2.1 and WooCommerce Subscriptions 9.3.0 on WordPress 7.1.3. Those marked **(7.1.4)** come from a run on WordPress 7.1.4 with WooCommerce 11.2.1: what a builder saw in the browser, in the editor or in WooCommerce's source, reported in its hand-back and not checked a second time.

## Before building

- **Coming-soon mode** hides the store from the harness's logged-out requests (`SKILL.md` Phase 2, step 7).
- **The Studio validator does not register WooCommerce's blocks.** It skips them and everything inside them, and still reports the rest as all valid: a cart page validated `0/0`, and a `page-cart` template counted only its parts. Validate in the site's own block editor (`agents/section-builder.md` § Validate). **(7.1.4)**
- **The account and checkout pages refuse to be framed from another origin.** WooCommerce sends `X-Frame-Options: SAMEORIGIN` and `Content-Security-Policy: frame-ancestors 'self'` there, so a harness served from the design server cannot frame them: `h2bt.ready()` rejects with a cross-origin `SecurityError`. Load the harness from the WordPress origin (`visual-refinement.md` § What the harness cannot show), and for a logged-out state use a page with an isolated context, which has no session. A filled cart needs the same, because its state is in a cookie. **(7.1.4)**

## Stylesheets: WooCommerce's print after the theme's

- **A theme rule needs strictly higher specificity than WooCommerce's.** WooCommerce's block and classic stylesheets print after the theme's on-demand block stylesheets, so a rule that ties loses. Its form fields reach 0,4,1, its product button 0,3,0, and the Mini-Cart drawer's rows 0,4,1 (`table.wc-block-cart-items .wc-block-cart-items__row …`). Scope a restyle through the same chain. On account pages, `.woocommerce-page form .form-row input.input-text` is 0,3,2 and `.woocommerce-account main .woocommerce` 0,2,1. **(7.1.4)**
- **Leave `woocommerce-smallscreen.css` off the pages the design restyles.** Below 768px it right-aligns every `shop_table_responsive` cell with `!important`, hides `tbody th` (the order number) and prints `data-title` labels. The `woocommerce_enqueue_styles` filter removes it for those pages, which is less CSS than countering each `!important` rule. **(7.1.4)**
- **WooCommerce's clearfix becomes a flex item.** Its classic CSS gives `.woocommerce form .form-row` and `.woocommerce-account .woocommerce` `::before` and `::after` with `display: table`. Once the theme makes either a flex container they are flex items, and each adds a gap at its end: hide them. **(7.1.4)**
- **`woocommerce-blocktheme.css` caps the post title** at `max-width: 1000px` on the cart, checkout and account pages, whatever the constrained group around it says. A title band's H1 needs its own width there. **(7.1.4)**
- **Form controls inside WooCommerce's components draw in the browser's default font.** The quantity selector's buttons and input are Arial unless the theme sets `font-family: inherit`, and its `:focus` rule sets `outline: none`. Put the theme's focus ring back with a negative offset, because the selector clips its overflow. **(7.1.4)**

## Templates

- **WooCommerce's checkout template does not use the theme's header or footer.** Its `page-checkout` template puts WooCommerce's own `checkout-header` part at the top (the site title and a cart link) and has no footer; its cart and order-confirmation templates use the theme's `header` and `footer`. A store theme carries `templates/page-checkout.html`, WooCommerce's checkout body between the theme's parts:

  ```html
  <!-- wp:template-part {"slug":"header","tagName":"header"} /-->

  <!-- wp:woocommerce/page-content-wrapper {"page":"checkout"} -->
  <!-- wp:group {"metadata":{"name":"Main"},"tagName":"main","layout":{"type":"constrained"}} -->
  <main class="wp-block-group"><!-- wp:woocommerce/store-notices /-->

  <!-- wp:post-content {"align":"wide"} /--></main>
  <!-- /wp:group -->
  <!-- /wp:woocommerce/page-content-wrapper -->

  <!-- wp:template-part {"slug":"footer","tagName":"footer"} /-->
  ```

  A design that shows a cut-down checkout header gets a part of the theme's for it.
- **`woocommerce/page-content-wrapper` opens with unsaved edits in the Site Editor.** It sets `postId` and `postType` from its `page` attribute when the template loads. Discard them with `wp.data.dispatch( 'core' ).clearEntityRecordEdits( 'postType', 'wp_template', '<theme>//<slug>' )`, and never save: that would store this environment's page id in the template. **(7.1.4)**
- **`woocommerce/store-notices` prints an empty wrapper** (`.woocommerce-notices-wrapper`) when there is no notice, so the next block in a flow or constrained container still gets the block gap. Give that container `blockGap` 0: the notices carry 16px margins of their own. **(7.1.4)**

## Products

- **A static card layout can hold a product.** `woocommerce/single-product` accepts core blocks inside it (groups, an image, `core/details`, buttons) and gives them the product as `postId` context, so only `woocommerce/product-price` and `woocommerce/product-button` need to be bound to it. It saves as `<div class="wp-block-woocommerce-single-product alignwide woocommerce">`, and the product id is stored in the page's content: a content migration carries it, and another environment's product ids differ. Validated in the site's block editor. **(7.1.4)**
- **`woocommerce/product-button` has no label attribute.** Its text is `$product->add_to_cart_text()` (filter `woocommerce_product_add_to_cart_text`) and its `aria-label` is `$product->add_to_cart_description()` (filter `woocommerce_product_add_to_cart_description`). Filter both: relabelling only the text leaves an accessible name that does not contain the visible label (WCAG 2.5.3). After an add, its script replaces the label with "N in cart" and shows a "View cart" link under the button. Read in the source, and seen in the browser. **(7.1.4)**
- **`woocommerce/product-button` drops the theme's button border and line height.** Its stylesheet sets `border-style: none` and `line-height: inherit` on `.wp-block-button.wc-block-components-product-button .wc-block-components-product-button__button` (0,3,0), which beats `theme.json`'s button element. A block stylesheet for `woocommerce/product-button` that restores both makes it the theme's button again. **(7.1.4)**
- **`woocommerce_price_trim_zeros` reaches only prices WooCommerce formats in PHP.** The block cart and checkout format prices in the browser, so a product card's "$90" is "$90.00" there. The editor's previews of `product-price` and `product-button` also format in JavaScript, from the Store API, so the trim and the add-to-cart text filter show on the front end only. **(The editor previews: 7.1.4.)**
- **A product collection lays itself out.** `woocommerce/product-collection` takes a grid layout of its own, with per-viewport `columnCount` and `blockGap`, so a card grid that changes its columns at a breakpoint needs no CSS.
- **A product collection in a template or a part picks its products by a property, never by hand.** A hand-picked collection stores product ids, and ids differ per environment. One by a property editors control, such as Featured (`woocommerce/product-collection/featured`) ordered by `menu_order`, needs no ids. It shows the first N products that match. Rendered with 0, 1, 2, 3 and 4 Featured products:
  - with fewer than N, a fixed grid shows empty columns;
  - with none, the block prints nothing;
  - with more than N, the product order decides which show.

  Ties in the product order are broken by title, though the markup names only `menu_order`: the collection's query sorts by `menu_order ASC, post_title ASC`, or both descending (`ProductCollection\QueryBuilder`). Products that were never sorted all have `menu_order` 0, so among them the title order alone decides which N show. A review that reads only the markup reports the order as undefined; it is not. Read in WooCommerce 11.2.1's source.

  Out-of-stock products stay in the collection unless `woocommerceStockStatus` leaves out `outofstock`. The Featured flags are data: each environment needs them set, and the pull request says which.
- **One block without interactivity support in a product collection turns client-side navigation off for the whole page** (`ProductCollection\Controller::is_block_compatible()`): a block counts when its `block.json` has `supports.interactivity` set to `true`, or `clientNavigation: true`. Check each block type you put in a collection; filters and pagination then reload the page instead.
- **Product images are lazy, the first row included.** `woocommerce/product-image` prints `loading="lazy"` unless `woocommerce_product_image_loading_attr` returns `eager` or `auto` (WooCommerce 10.6 and later). A shop's first screen is then lazy whatever WordPress's threshold says: report it (`standards.md`).
- **A product image tile with text over it needs no custom block.** Inside `woocommerce/product-template`, a `core/cover` with `useFeaturedImage` renders each product's own featured image as its background.
- **Sample products are looked up by post type.** `get_page_by_path( $slug, OBJECT, 'product' )` also searches attachments (core adds them when the post type is a string), and a product named like its image ("Lavender Oil", `lavender-oil.png`) resolves to the image. Pass `array( 'product' )`, or use `get_posts( array( 'post_type' => 'product', 'name' => $slug ) )`.
- **A change to the thumbnail options takes effect on the next request.** WooCommerce registers its image sizes at `init`, so after changing `woocommerce_thumbnail_cropping` and its ratio, regenerate the attachments' metadata in a second `eval-file` run: in the same request they are cut to the old size. **(7.1.4)**

### WooCommerce Subscriptions

- **Subscriptions' plan options need the classic add-to-cart form on a product with variations.** In `woocommerce/add-to-cart-with-options` Subscriptions prints no plan options for such a product: they travel in each variation's price HTML, which only the classic variation script swaps in. `woocommerce/add-to-cart-form` prints them. Its default layout puts a one-time/subscribe choice with neither radio checked above the plans; four filters give one list:
  - `wcsatt_subscription_options_layout` returning `'flat'`;
  - `wcsatt_single_product_options` to order the options;
  - `wcsatt_get_default_subscription_scheme_id` to preselect a plan;
  - `wcsatt_single_product_one_time_option_has_price` to show the one-time price.

  For a simple product the block form prints the options; whether its add-to-cart submits the chosen plan was not checked.
- **Make the variation area a polite live region.** WooCommerce prints it as `<div class="woocommerce-variation single_variation" role="alert">`, and Subscriptions draws its plan options inside it, so every change of variation announced the whole list of options. Make it `role="status"`, with a `render_block_woocommerce/add-to-cart-form` filter and `WP_HTML_Tag_Processor`. Found in an accessibility review; not checked with a screen reader.
- **A script that reads the variation form can read the previous variation.** WooCommerce shows a chosen variation's options about 300ms after the choice, and Subscriptions then redraws the options and the button's label, so for that moment the form still holds the previous variation's price. Take the price from the `found_variation` event's data, and check that its `variation_id` still matches the form's. Seen in the browser, with quick changes of variation.

## Cart

- **Write the totals wrapper into the cart's markup.** The cart editor wraps subtotal, fee, discount, shipping and taxes in `woocommerce/cart-order-summary-totals-block`, in that order. The cart page WooCommerce's installer creates lacks it: PHP wraps them on render and the editor migrates the page when it loads, so a page written without it opens with unsaved changes. **(7.1.4)**
- **A cart inner block's attributes live only in its block comment** (a heading's `content`, proceed-to-checkout's `buttonLabel`). PHP prints them as `data-*` attributes on the inner block's `div`, and the front end reads them there. Confirm one with `render-probe.sh` before relying on it. **(7.1.4)**
- **The Check Out button is hidden on desktop until the visitor scrolls near it.** Its container gets `wc-block-cart__submit-container--sticky` while its sentinel is below the viewport; `cart.css` hides that class from 783px up and fixes it to the bottom of the viewport below 783px. In a hidden or background tab (the harness) it measures 0×0. A design that shows the button in place sets the sticky container to `position: static` and `display: block`. `.wc-block-cart__submit` also carries a 16px bottom margin. **(7.1.4)**

## Checkout

- **The billing step renames itself.** With `woocommerce_ship_to_destination` set to `billing_only` and a cart that needs shipping, the front end replaces a title equal to the default ("Billing address") with "Billing and shipping address", and an empty description with "Enter the billing and shipping address that matches your payment method.". The editor drops an attribute equal to its default, so only a title that differs from the default can be stored. **(7.1.4)**
- **Below a 920px container the order summary is drawn twice.** The sidebar collapses to a toggle (`role=button`, its content `display: none`), and an open copy of the summary renders inside the actions block (`.checkout-order-summary-block-fill-wrapper > .checkout-order-summary-block-fill`) above Place Order. Both copies carry `.wp-block-woocommerce-checkout-order-summary-block`, so one rule set styles both. To show one open card, hide the collapsed sidebar with `.wc-block-components-sidebar-layout:has(.checkout-order-summary-block-fill) > .wc-block-checkout__sidebar`. **(7.1.4)**
- **The address form is a flex container only from a 400px container up.** Below that it is `display: block`, and a gap the theme sets on it disappears. Set `display: flex` and `flex-wrap` yourself when spacing its fields with `gap`, scoped to the billing and shipping forms: the contact step's address form also holds the guest-checkout paragraph. **(7.1.4)**
- **A text field prints its label after its input.** For labels above the fields, make the wrapper a flex column and give the label `order: -1`; `column-reverse` would also move the validation message. The coupon input is a `.wc-block-components-text-input` too, and in the narrow-screen summary copy it sits inside the checkout form: exclude it. **(7.1.4)**
- **Spacing WooCommerce adds:** `.wc-block-checkout` has a 24px top padding and `.wc-block-checkout__actions` a 36px bottom margin. "You are currently checking out as a guest." prints whenever guest checkout is allowed (`checkoutAllowsGuest`), whatever the sign-up settings. **(7.1.4)**
- **Measure after the Store API answers.** The checkout first renders skeleton summary lines and a loading payment step, and re-renders when the Store API answers, one to three seconds later: the summary card grew by 74px and the payment step by 31px. **(7.1.4)**
- **The error state can be shown without placing an order:** `wp.data.dispatch( 'wc/store/validation' ).showAllValidationErrors()`. **(7.1.4)**
- **The order summary's screen-reader text reads the Store API's encoded product name:** a product named "Salt & Pepper" is announced as "Salt &#038; Pepper". Report it; the theme cannot change it. **(7.1.4)**

## My Account

- **WooCommerce's account template hooks exist on front-end requests only.** `woocommerce_account_content` and its siblings are added when the plugin loads on a front-end request, so a theme can replace a callback on `init`. `remove_action()`'s return value tells a front-end request from an admin or REST one. **(7.1.4)**
- **Reusing `myaccount/orders.php` outside the Orders endpoint also prints the guest-order email prompt** (WooCommerce 11, hooked on `woocommerce_before_account_orders`). The `woocommerce_customer_email_verification_should_show_prompt` filter turns it off for that render. **(7.1.4)**
- **WooCommerce adds a "Show password" button inside the password field** by script. A measurement or a rule that selects `form button` gets it before the submit button. **(7.1.4)**
- **An account page's title can change without touching the menu.** A `the_title` filter scoped as WooCommerce scopes its own (`is_main_query()`, `in_the_loop()`, and the post id equal to the queried object) changes `core/post-title` and leaves navigation link labels alone; `document_title_parts` carries the same title to the browser tab. **(7.1.4)**

## Mini-Cart

- **The closed Mini-Cart drawer leaves Tab stops.** WooCommerce prints the drawer in `wp_footer`, hidden with `aria-hidden` only, so its buttons stay in the Tab order. Bind `inert` to its open state with `data-wp-bind--inert="!state.isOpen"` on `.wc-block-mini-cart__drawer`, and print `inert` on the closed drawer so that it holds before the page hydrates. Add both to the footer's output with `WP_HTML_Tag_Processor`. Checked with the keyboard. The drawer is echoed at `wp_footer` priority 10, so an output buffer opened at 9 and closed at 11 holds it. **(The priority: 7.1.4.)**
- **The Mini-Cart's store has no state on the cart and checkout pages.** There `MiniCart::render()` returns a hidden, disabled button, or nothing, before it loads the cart state. Markup that reads `woocommerce/mini-cart` elsewhere, such as a cart count in the header, needs a static fallback on those two pages (`custom-blocks-guide.md` § What a block can know). Read in WooCommerce 11.2.1's source.
- **What the drawer adds:** an empty notices `div` above the drawer's title carries a 16px top margin; below 480px the footer's help text is `display: none` and the actions stack in a column. **(7.1.4)**

## In a project repository

- **The project template's PHPStan has no WooCommerce stubs.** A hook callback typed `\WC_Product` fails level 8 with `class.notFound`. Type the product `mixed`, check it with `is_object()` and `method_exists()`, and compare results with `true ===` for the strict rules. **(7.1.4)**
