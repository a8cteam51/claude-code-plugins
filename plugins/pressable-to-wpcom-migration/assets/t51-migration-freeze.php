<?php
/**
 * Plugin Name: Team 51 Migration Freeze
 * Description: Makes the live site read-only for the final sync of a migration. Runtime filters only: nothing is written to the database, so deleting this file lifts the freeze.
 * Version: 0.1.0
 *
 * Installed on the migration SOURCE (the Pressable site) at the start of the
 * cutover window. It stays in place after cutover so visitors whose DNS has
 * not updated cannot create data on the old site.
 *
 * Two modes, chosen when the file is installed:
 *   drain   new checkouts, forms, comments and registrations are refused, but
 *           payment-gateway callbacks and scheduled jobs still run, so orders
 *           already in flight can finish. Use for a few minutes first on stores.
 *   frozen  everything that writes is refused and scheduled jobs are paused.
 *           The final sync runs in this mode.
 *
 * Pages stay browsable in both modes. Administrators can still log in and work
 * (they should not, during the window). Jetpack and Reprint requests are let
 * through so the export keeps working.
 *
 * STATUS: draft, not yet proven on a real migration.
 */

defined( 'ABSPATH' ) || exit;

if ( ! defined( 'T51_FREEZE_MODE_DEFAULT' ) ) {
	define( 'T51_FREEZE_MODE_DEFAULT', '__T51_FREEZE_MODE__' );
}

function t51_freeze_mode() {
	$mode = defined( 'T51_FREEZE_MODE' ) ? T51_FREEZE_MODE : T51_FREEZE_MODE_DEFAULT;
	return in_array( $mode, array( 'drain', 'frozen' ), true ) ? $mode : 'frozen';
}

function t51_freeze_message() {
	return 'We are carrying out scheduled maintenance. Ordering, forms, comments and sign-in are unavailable for a short time. Please try again later.';
}

/* Requests that must keep working: the export itself, Jetpack, and command-line use. */
function t51_freeze_is_exempt() {
	if ( ( defined( 'WP_CLI' ) && WP_CLI ) || isset( $_GET['reprint-api'] ) || isset( $_GET['reprint-api-jetpack'] ) || isset( $_GET['site-export-api'] ) ) { // phpcs:ignore
		return true;
	}
	$uri = isset( $_SERVER['REQUEST_URI'] ) ? (string) $_SERVER['REQUEST_URI'] : ''; // phpcs:ignore
	if ( false !== strpos( $uri, 'xmlrpc.php' ) && isset( $_GET['for'] ) && 'jetpack' === $_GET['for'] ) { // phpcs:ignore
		return true;
	}
	if ( preg_match( '#/wp-json/(jetpack|wpcom|my-jetpack)/#', $uri ) || ( isset( $_GET['rest_route'] ) && preg_match( '#^/(jetpack|wpcom|my-jetpack)/#', (string) $_GET['rest_route'] ) ) ) { // phpcs:ignore
		return true;
	}
	/* Payment-gateway callbacks are let through only while draining. */
	if ( 'drain' === t51_freeze_mode() && ( isset( $_GET['wc-api'] ) || false !== strpos( $uri, '/wc-api/' ) || preg_match( '#/wp-json/(wc/v\d+/payments|wc/v\d+/wcpay|wc-stripe|paypal|wc/v\d+/square)#', $uri ) ) ) { // phpcs:ignore
		return true;
	}
	return false;
}

function t51_freeze_refuse() {
	if ( ! headers_sent() ) {
		status_header( 503 );
		header( 'Retry-After: 1800' );
		nocache_headers();
	}
	if ( ( defined( 'REST_REQUEST' ) && REST_REQUEST ) || ( defined( 'DOING_AJAX' ) && DOING_AJAX ) || false !== strpos( isset( $_SERVER['HTTP_ACCEPT'] ) ? (string) $_SERVER['HTTP_ACCEPT'] : '', 'application/json' ) ) { // phpcs:ignore
		wp_send_json( array( 'code' => 't51_migration_freeze', 'message' => t51_freeze_message() ), 503 );
	}
	wp_die( esc_html( t51_freeze_message() ), 'Scheduled maintenance', array( 'response' => 503 ) );
}

/* Refuse anything that is not a read, unless the visitor is an administrator. */
add_action(
	'init',
	function () {
		if ( t51_freeze_is_exempt() ) {
			return;
		}
		$method = isset( $_SERVER['REQUEST_METHOD'] ) ? strtoupper( (string) $_SERVER['REQUEST_METHOD'] ) : 'GET'; // phpcs:ignore
		if ( in_array( $method, array( 'GET', 'HEAD', 'OPTIONS' ), true ) ) {
			return;
		}
		if ( current_user_can( 'manage_options' ) ) {
			return;
		}
		$uri = isset( $_SERVER['REQUEST_URI'] ) ? (string) $_SERVER['REQUEST_URI'] : ''; // phpcs:ignore
		/* Let the login form post so administrators can get in; non-administrators are refused below. */
		if ( false !== strpos( $uri, 'wp-login.php' ) ) {
			return;
		}
		t51_freeze_refuse();
	},
	0
);

/* Only administrators may sign in. */
add_filter(
	'authenticate',
	function ( $user ) {
		if ( $user instanceof WP_User && ! user_can( $user, 'manage_options' ) ) {
			return new WP_Error( 't51_migration_freeze', t51_freeze_message() );
		}
		return $user;
	},
	100
);

/* Belt and braces for the common write paths, in case something bypasses the request check. */
add_filter( 'comments_open', '__return_false', PHP_INT_MAX );
add_filter( 'pings_open', '__return_false', PHP_INT_MAX );
add_filter( 'pre_option_users_can_register', '__return_zero', PHP_INT_MAX );
add_filter( 'woocommerce_available_payment_gateways', '__return_empty_array', PHP_INT_MAX );
add_filter(
	'woocommerce_no_available_payment_methods_message',
	function () {
		return t51_freeze_message();
	}
);

/* Frozen: scheduled work stops too, so nothing (renewals, queued emails) changes data after the final sync. */
if ( 'frozen' === t51_freeze_mode() ) {
	add_filter( 'pre_get_ready_cron_jobs', '__return_empty_array', PHP_INT_MAX );
	add_filter( 'action_scheduler_queue_runner_concurrent_batches', '__return_zero', PHP_INT_MAX );
	add_filter( 'action_scheduler_allow_async_request_runner', '__return_false', PHP_INT_MAX );
	add_filter( 'woocommerce_webhook_should_deliver', '__return_false', PHP_INT_MAX );
}

/* Tell visitors, and tell administrators which mode is on. */
add_action(
	'wp_footer',
	function () {
		echo '<div style="position:fixed;left:0;right:0;bottom:0;z-index:99999;background:#1d2327;color:#fff;padding:10px 16px;font:14px/1.4 sans-serif;text-align:center">'
			. esc_html( t51_freeze_message() ) . '</div>';
	}
);
add_action(
	'admin_notices',
	function () {
		echo '<div class="notice notice-error"><p><strong>Migration freeze is on (' . esc_html( t51_freeze_mode() ) . ').</strong> Do not edit content: changes made now will not reach the new site.</p></div>';
	}
);

add_action(
	'rest_api_init',
	function () {
		register_rest_route(
			't51-migration/v1',
			'/freeze',
			array(
				'methods'             => 'GET',
				'permission_callback' => '__return_true',
				'callback'            => function () {
					return array( 'active' => true, 'mode' => t51_freeze_mode(), 'version' => '0.1.0' );
				},
			)
		);
	}
);
