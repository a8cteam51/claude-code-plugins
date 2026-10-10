<?php
/**
 * Plugin Name: Team 51 Migration Quarantine
 * Description: Keeps a migrated copy quiet until cutover. Runtime filters only: nothing is written to the database, so deleting this file restores normal behaviour. NOT SafetyNet: no data is deleted or scrubbed.
 * Version: 0.1.0
 *
 * Installed on the migration TARGET (the new WordPress.com site) before the
 * first sync, removed at cutover.
 *
 * While active it:
 *   - blocks outgoing email sent through wp_mail();
 *   - stops WP-Cron events and Action Scheduler from running;
 *   - stops WooCommerce webhooks from being delivered;
 *   - offers no payment gateways, so checkout cannot complete;
 *   - asks search engines not to index the copy;
 *   - shows administrators a banner.
 *
 * It switches itself off when the site's home URL is no longer a temporary
 * WordPress.com address, so a forgotten copy cannot cripple a launched site.
 * Force it either way with define( 'T51_MIGRATION_QUARANTINE', true|false ).
 *
 * Not covered: plugins that send mail or call APIs without wp_mail() or the
 * WordPress scheduler. Check the audit's list of integrations.
 *
 * STATUS: draft, not yet proven on a real migration.
 */

defined( 'ABSPATH' ) || exit;

function t51_quarantine_active() {
	if ( defined( 'T51_MIGRATION_QUARANTINE' ) ) {
		return (bool) T51_MIGRATION_QUARANTINE;
	}
	$host = (string) wp_parse_url( get_option( 'home' ), PHP_URL_HOST );
	return (bool) preg_match( '/\.(wpcomstaging\.com|wordpress\.com|wpcomstaging\.net|mystagingwebsite\.com)$/', $host );
}

if ( ! t51_quarantine_active() ) {
	return;
}

/* Email. Returning non-null short-circuits wp_mail() without sending. */
add_filter(
	'pre_wp_mail',
	function ( $return, $atts ) {
		error_log( 't51-quarantine: blocked email "' . ( isset( $atts['subject'] ) ? $atts['subject'] : '' ) . '"' ); // phpcs:ignore
		return false;
	},
	PHP_INT_MAX,
	2
);

/* WP-Cron: nothing is ever "ready", for wp-cron.php and for `wp cron event run`. */
add_filter( 'pre_get_ready_cron_jobs', '__return_empty_array', PHP_INT_MAX );

/* Action Scheduler: zero allowed batches means the queue runner never claims work. */
add_filter( 'action_scheduler_queue_runner_concurrent_batches', '__return_zero', PHP_INT_MAX );
add_filter( 'action_scheduler_allow_async_request_runner', '__return_false', PHP_INT_MAX );

/* WooCommerce: no webhook deliveries, no way to pay. */
add_filter( 'woocommerce_webhook_should_deliver', '__return_false', PHP_INT_MAX );
add_filter( 'woocommerce_available_payment_gateways', '__return_empty_array', PHP_INT_MAX );
add_filter(
	'woocommerce_no_available_payment_methods_message',
	function () {
		return 'This is a migration copy of the site. Checkout is switched off.';
	}
);

/* Search engines. Filtered at read time; the stored option is untouched. */
add_filter( 'pre_option_blog_public', '__return_zero', PHP_INT_MAX );
add_action(
	'send_headers',
	function () {
		header( 'X-Robots-Tag: noindex, nofollow', true );
	}
);

/* Tell administrators what they are looking at. */
function t51_quarantine_banner() {
	if ( ! current_user_can( 'manage_options' ) ) {
		return;
	}
	echo '<div style="position:relative;z-index:99999;background:#b32d2e;color:#fff;padding:8px 16px;font:14px/1.4 sans-serif;text-align:center">'
		. 'Migration quarantine is on: email, scheduled jobs, webhooks and checkout are switched off on this copy.</div>';
}
add_action( 'admin_notices', 't51_quarantine_banner' );
add_action( 'wp_footer', 't51_quarantine_banner' );

/* Machine-readable status for the verify scripts. */
add_action(
	'rest_api_init',
	function () {
		register_rest_route(
			't51-migration/v1',
			'/quarantine',
			array(
				'methods'             => 'GET',
				'permission_callback' => '__return_true',
				'callback'            => function () {
					return array( 'active' => true, 'version' => '0.1.0' );
				},
			)
		);
	}
);
