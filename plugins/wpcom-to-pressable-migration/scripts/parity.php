<?php
/**
 * Read-only data fingerprint, run on source and target and compared with
 * compare_parity.py. Counts, highest IDs and latest change times for the data
 * a migration must not lose.
 *
 * Arguments ($t51_args): { "since": "2026-10-10 14:00:00" }  (optional, GMT)
 * With "since", also counts rows written after that time: the straggler check.
 */

global $wpdb;
$since = isset( $t51_args['since'] ) ? (string) $t51_args['since'] : null;
$exists = function ( $table ) use ( $wpdb ) {
	return $wpdb->get_var( $wpdb->prepare( 'SHOW TABLES LIKE %s', $table ) ) === $table;
};
$row = function ( $sql ) use ( $wpdb ) {
	$wpdb->suppress_errors( true );
	$r = $wpdb->get_row( $sql, ARRAY_A );
	$wpdb->suppress_errors( false );
	return $r ? $r : array();
};
$px  = $wpdb->prefix;
$out = array(
	'collected_at' => gmdate( 'Y-m-d H:i:s' ),
	'home'         => home_url(),
	'siteurl'      => site_url(),
	'table_prefix' => $px,
	'data'         => array(),
	'after_since'  => array(),
);

$out['data']['posts']    = $row( "SELECT COUNT(*) AS n, MAX(ID) AS max_id, MAX(post_modified_gmt) AS latest FROM {$wpdb->posts} WHERE post_type NOT IN ('revision','scheduled-action') AND post_status <> 'auto-draft'" );
$out['data']['comments'] = $row( "SELECT COUNT(*) AS n, MAX(comment_ID) AS max_id, MAX(comment_date_gmt) AS latest FROM {$wpdb->comments}" );
$out['data']['users']    = $row( "SELECT COUNT(*) AS n, MAX(ID) AS max_id, MAX(user_registered) AS latest FROM {$wpdb->users}" );
$out['data']['terms']    = $row( "SELECT COUNT(*) AS n, MAX(term_id) AS max_id FROM {$wpdb->terms}" );
$out['data']['postmeta'] = $row( "SELECT COUNT(*) AS n, MAX(meta_id) AS max_id FROM {$wpdb->postmeta}" );
$out['data']['usermeta'] = $row( "SELECT COUNT(*) AS n, MAX(umeta_id) AS max_id FROM {$wpdb->usermeta}" );
$out['data']['attachments'] = $row( "SELECT COUNT(*) AS n, MAX(ID) AS max_id FROM {$wpdb->posts} WHERE post_type = 'attachment'" );

if ( $exists( $px . 'wc_orders' ) ) {
	$out['data']['wc_orders']      = $row( "SELECT COUNT(*) AS n, MAX(id) AS max_id, MAX(date_updated_gmt) AS latest FROM {$px}wc_orders" );
	$out['data']['wc_order_items'] = $row( "SELECT COUNT(*) AS n, MAX(order_item_id) AS max_id FROM {$px}woocommerce_order_items" );
}
if ( $exists( $px . 'woocommerce_order_items' ) && ! isset( $out['data']['wc_order_items'] ) ) {
	$out['data']['wc_order_items'] = $row( "SELECT COUNT(*) AS n, MAX(order_item_id) AS max_id FROM {$px}woocommerce_order_items" );
}
$out['data']['legacy_orders'] = $row( "SELECT COUNT(*) AS n, MAX(ID) AS max_id, MAX(post_modified_gmt) AS latest FROM {$wpdb->posts} WHERE post_type IN ('shop_order','shop_subscription','shop_order_refund')" );
foreach ( array( 'wc_customer_lookup' => 'customer_id', 'woocommerce_payment_tokens' => 'token_id', 'wc_webhooks' => 'webhook_id', 'woocommerce_api_keys' => 'key_id', 'frm_items' => 'id', 'gf_entry' => 'id', 'wpforms_entries' => 'entry_id', 'redirection_items' => 'id', 'mailpoet_subscribers' => 'id', 'zbs_contacts' => 'ID', 'slicewp_commissions' => 'id' ) as $table => $pk ) {
	if ( $exists( $px . $table ) ) {
		$out['data'][ $table ] = $row( "SELECT COUNT(*) AS n, MAX(`{$pk}`) AS max_id FROM `{$px}{$table}`" );
	}
}

/* Every table's exact row count, so a table the target lacks stands out. */
$out['tables'] = array();
foreach ( (array) $wpdb->get_col( $wpdb->prepare( 'SHOW TABLES LIKE %s', $wpdb->esc_like( $px ) . '%' ) ) as $table ) {
	$short = substr( $table, strlen( $px ) );
	/* Queues, logs and caches differ between any two running copies. */
	if ( preg_match( '/^(actionscheduler_|jetpack_sync_queue|wc_admin_note|woocommerce_sessions|woocommerce_log|wc_rate_limits|redirection_404|redirection_logs|wpml_mails|wfhits|wflogs|a8csp_|e_events|yoast_indexable|wc_product_meta_lookup$)/', $short ) ) {
		continue;
	}
	$out['tables'][ $short ] = (int) $wpdb->get_var( "SELECT COUNT(*) FROM `{$table}`" );
}

$out['options'] = array(
	'active_plugins'  => array_values( (array) get_option( 'active_plugins' ) ),
	'stylesheet'      => get_option( 'stylesheet' ),
	'template'        => get_option( 'template' ),
	'permalinks'      => get_option( 'permalink_structure' ),
	'blog_public'     => get_option( 'blog_public' ),
	'admin_email'     => get_option( 'admin_email' ),
	'jetpack_blog_id' => is_array( get_option( 'jetpack_options' ) ) && isset( get_option( 'jetpack_options' )['id'] ) ? (int) get_option( 'jetpack_options' )['id'] : null,
	'options_count'   => (int) $wpdb->get_var( "SELECT COUNT(*) FROM {$wpdb->options} WHERE option_name NOT LIKE '\_transient\_%' AND option_name NOT LIKE '\_site\_transient\_%'" ),
	'environment'     => function_exists( 'wp_get_environment_type' ) ? wp_get_environment_type() : null,
);

/* URLs that still point somewhere unexpected after a sync. */
$host = wp_parse_url( home_url(), PHP_URL_HOST );
$probe = isset( $t51_args['other_host'] ) ? (string) $t51_args['other_host'] : null;
if ( $probe && $probe !== $host ) {
	$like = '%' . $wpdb->esc_like( '//' . $probe ) . '%';
	$out['other_host_references'] = array(
		'host'     => $probe,
		'posts'    => (int) $wpdb->get_var( $wpdb->prepare( "SELECT COUNT(*) FROM {$wpdb->posts} WHERE post_content LIKE %s AND post_type <> 'revision'", $like ) ),
		'postmeta' => (int) $wpdb->get_var( $wpdb->prepare( "SELECT COUNT(*) FROM {$wpdb->postmeta} WHERE meta_value LIKE %s", $like ) ),
		'options'  => (int) $wpdb->get_var( $wpdb->prepare( "SELECT COUNT(*) FROM {$wpdb->options} WHERE option_value LIKE %s AND option_name NOT LIKE '\_transient\_%'", $like ) ),
	);
}

if ( $since ) {
	$out['after_since']['since']    = $since;
	$out['after_since']['posts']    = (int) $wpdb->get_var( $wpdb->prepare( "SELECT COUNT(*) FROM {$wpdb->posts} WHERE post_modified_gmt > %s AND post_type NOT IN ('revision','scheduled-action') AND post_status <> 'auto-draft'", $since ) );
	$out['after_since']['comments'] = (int) $wpdb->get_var( $wpdb->prepare( "SELECT COUNT(*) FROM {$wpdb->comments} WHERE comment_date_gmt > %s", $since ) );
	$out['after_since']['users']    = (int) $wpdb->get_var( $wpdb->prepare( "SELECT COUNT(*) FROM {$wpdb->users} WHERE user_registered > %s", $since ) );
	if ( $exists( $px . 'wc_orders' ) ) {
		$out['after_since']['wc_orders'] = (int) $wpdb->get_var( $wpdb->prepare( "SELECT COUNT(*) FROM {$px}wc_orders WHERE date_updated_gmt > %s", $since ) );
	}
	foreach ( array( 'frm_items' => 'created_at', 'gf_entry' => 'date_created', 'wpforms_entries' => 'date' ) as $table => $col ) {
		if ( $exists( $px . $table ) ) {
			$out['after_since'][ $table ] = (int) $wpdb->get_var( $wpdb->prepare( "SELECT COUNT(*) FROM `{$px}{$table}` WHERE `{$col}` > %s", $since ) );
		}
	}
}

t51_emit( $out );
