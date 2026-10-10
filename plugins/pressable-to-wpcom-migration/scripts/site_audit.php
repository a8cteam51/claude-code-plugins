<?php
/**
 * Read-only site inventory for the Pressable -> WordPress.com migration audit.
 *
 * Runs inside `wp eval` through scripts/wp_eval.sh, which strips this opening
 * tag. It prints one JSON document between the markers below and changes
 * nothing on the site.
 *
 * Secrets: never print option values that hold tokens, keys or passwords.
 * Constants are reported by name only, apart from a short allow-list.
 */

global $wpdb, $wp_version;
require_once ABSPATH . 'wp-admin/includes/plugin.php';

$out = array( 'schema' => 1, 'collected_at' => gmdate( 'c' ) );

$count = function ( $sql ) use ( $wpdb ) {
	$wpdb->suppress_errors( true );
	$value = $wpdb->get_var( $sql );
	$wpdb->suppress_errors( false );
	return null === $value ? null : (int) $value;
};
$table_exists = function ( $table ) use ( $wpdb ) {
	return $wpdb->get_var( $wpdb->prepare( 'SHOW TABLES LIKE %s', $table ) ) === $table;
};

/* ---------- Core ---------- */
$out['core'] = array(
	'home'             => home_url(),
	'siteurl'          => site_url(),
	'wp_version'       => $wp_version,
	'php_version'      => PHP_VERSION,
	'multisite'        => is_multisite(),
	'table_prefix'     => $wpdb->prefix,
	'environment_type' => function_exists( 'wp_get_environment_type' ) ? wp_get_environment_type() : null,
	'is_pressable'     => defined( 'IS_PRESSABLE' ) && IS_PRESSABLE,
	'is_atomic'        => defined( 'IS_ATOMIC' ) && IS_ATOMIC,
	'blog_public'      => get_option( 'blog_public' ),
	'permalinks'       => get_option( 'permalink_structure' ),
	'timezone'         => wp_timezone_string(),
	'admin_email'      => get_option( 'admin_email' ),
	'abspath'          => ABSPATH,
	'content_dir'      => WP_CONTENT_DIR,
	'locale'           => get_locale(),
);

/* ---------- Plugins, mu-plugins, drop-ins, themes ---------- */
$out['plugins'] = array();
foreach ( get_plugins() as $file => $p ) {
	$out['plugins'][] = array(
		'file'       => $file,
		'slug'       => false !== strpos( $file, '/' ) ? dirname( $file ) : basename( $file, '.php' ),
		'name'       => $p['Name'],
		'version'    => $p['Version'],
		'author'     => wp_strip_all_tags( $p['Author'] ),
		'active'     => is_plugin_active( $file ),
		'update_uri' => isset( $p['UpdateURI'] ) ? $p['UpdateURI'] : '',
		'woo'        => isset( $p['Woo'] ) ? $p['Woo'] : '',
	);
}
$out['mu_plugins'] = array(
	'files' => array_keys( get_mu_plugins() ),
	'dirs'  => is_dir( WPMU_PLUGIN_DIR ) ? array_values( array_map( 'basename', (array) glob( WPMU_PLUGIN_DIR . '/*', GLOB_ONLYDIR ) ) ) : array(),
);
$out['dropins'] = array_keys( get_dropins() );

$theme         = wp_get_theme();
$out['themes'] = array(
	'active'    => $theme->get_stylesheet(),
	'parent'    => $theme->get_template(),
	'version'   => $theme->get( 'Version' ),
	'author'    => wp_strip_all_tags( (string) $theme->get( 'Author' ) ),
	'is_block'  => function_exists( 'wp_is_block_theme' ) ? wp_is_block_theme() : null,
	'installed' => array_keys( wp_get_themes() ),
);

/* ---------- Files outside wp-content that the migration will not carry ---------- */
$core_root = array( 'index.php', 'xmlrpc.php', 'wp-activate.php', 'wp-blog-header.php', 'wp-comments-post.php', 'wp-config.php', 'wp-config-sample.php', 'wp-cron.php', 'wp-links-opml.php', 'wp-load.php', 'wp-login.php', 'wp-mail.php', 'wp-settings.php', 'wp-signup.php', 'wp-trackback.php' );
$roots     = array_unique( array( rtrim( dirname( WP_CONTENT_DIR ), '/' ), rtrim( ABSPATH, '/' ) ) );
$extra     = array();
foreach ( $roots as $root ) {
	foreach ( (array) glob( $root . '/{*.php,.htaccess,*.txt,*.html,*.xml,*.ini}', GLOB_BRACE ) as $path ) {
		$base = basename( $path );
		if ( in_array( $base, $core_root, true ) || in_array( $base, array( 'license.txt', 'readme.html' ), true ) ) {
			continue;
		}
		$extra[ $root . '/' . $base ] = array( 'path' => $path, 'bytes' => (int) @filesize( $path ), 'modified' => gmdate( 'Y-m-d', (int) @filemtime( $path ) ) );
	}
}
$out['root_files'] = array_values( $extra );

/* wp-content entries that are not the standard directories. */
$standard_content   = array( 'plugins', 'themes', 'mu-plugins', 'uploads', 'languages', 'upgrade', 'upgrade-temp-backup', 'cache', 'index.php', 'object-cache.php', 'advanced-cache.php', 'db.php', 'fonts' );
$out['content_extras'] = array_values( array_diff( array_map( 'basename', (array) glob( WP_CONTENT_DIR . '/*' ) ), $standard_content ) );

/* Host files on Reprint's Pressable / WP Cloud cleanup list. */
$host_paths = array( 'mu-plugins/pcm-extend-batcache.php', 'mu-plugins/pcm-exclude-pages-from-batcache.php', 'plugins/pressable-cache-management', 'plugins/pressable-onepress-login', 'object-cache.php', 'advanced-cache.php', 'mu-plugins/wpcomsh', 'mu-plugins/wpcomsh-loader.php' );
$out['host_files'] = array_values( array_filter( $host_paths, function ( $p ) {
	return file_exists( WP_CONTENT_DIR . '/' . $p );
} ) );

/* ---------- Constants: names only, plus an allow-list of harmless values ---------- */
$safe_value = array( 'WP_ENVIRONMENT_TYPE', 'WP_MEMORY_LIMIT', 'WP_MAX_MEMORY_LIMIT', 'DISABLE_WP_CRON', 'WP_CACHE', 'WP_DEBUG', 'WP_DEBUG_LOG', 'WP_DEBUG_DISPLAY', 'FORCE_SSL_ADMIN', 'DISALLOW_FILE_EDIT', 'DISALLOW_FILE_MODS', 'WP_POST_REVISIONS', 'AUTOSAVE_INTERVAL', 'EMPTY_TRASH_DAYS', 'WP_AUTO_UPDATE_CORE', 'AUTOMATIC_UPDATER_DISABLED', 'WP_CRON_LOCK_TIMEOUT', 'CONCATENATE_SCRIPTS', 'MULTISITE', 'SUBDOMAIN_INSTALL', 'JETPACK_STAGING_MODE', 'JETPACK_DEV_DEBUG', 'WPC_BOT_PROTECTION_ENABLED', 'SAFETY_NET_DELETE_DATA', 'SAFETY_NET_KEEP_UNTIL', 'WP_DEFAULT_THEME', 'WP_HOME', 'WP_SITEURL', 'COOKIE_DOMAIN', 'IS_PRESSABLE', 'IS_ATOMIC', 'ATOMIC_SITE_ID', 'ATOMIC_CLIENT_ID' );
$defined_in_config = array();
$config_path       = file_exists( ABSPATH . 'wp-config.php' ) ? ABSPATH . 'wp-config.php' : ( file_exists( dirname( ABSPATH ) . '/wp-config.php' ) ? dirname( ABSPATH ) . '/wp-config.php' : null );
foreach ( array_filter( array_unique( array( $config_path, dirname( WP_CONTENT_DIR ) . '/wp-config.php' ) ) ) as $cfg ) {
	if ( is_readable( $cfg ) && preg_match_all( '/^\s*define\s*\(\s*[\'"]([A-Za-z0-9_]+)[\'"]/m', (string) file_get_contents( $cfg ), $m ) ) {
		$defined_in_config = array_merge( $defined_in_config, $m[1] );
	}
}
$out['constants'] = array( 'in_wp_config' => array(), 'config_path' => $config_path );
foreach ( array_unique( $defined_in_config ) as $name ) {
	if ( preg_match( '/^(ABSPATH|DB_|AUTH_KEY|SECURE_AUTH_KEY|LOGGED_IN_KEY|NONCE_KEY|AUTH_SALT|SECURE_AUTH_SALT|LOGGED_IN_SALT|NONCE_SALT)/', $name ) ) {
		continue;
	}
	$entry = array( 'name' => $name );
	if ( in_array( $name, $safe_value, true ) && defined( $name ) ) {
		$entry['value'] = constant( $name );
	}
	$out['constants']['in_wp_config'][] = $entry;
}
/* ---------- Jetpack ---------- */
$jp            = array( 'installed' => class_exists( 'Jetpack' ), 'version' => defined( 'JETPACK__VERSION' ) ? JETPACK__VERSION : null );
$jp_options    = get_option( 'jetpack_options' );
$jp['blog_id'] = is_array( $jp_options ) && isset( $jp_options['id'] ) ? (int) $jp_options['id'] : null;
$jp['master_user_local_id'] = is_array( $jp_options ) && isset( $jp_options['master_user'] ) ? (int) $jp_options['master_user'] : null;
$jp['active_modules']       = array_values( (array) get_option( 'jetpack_active_modules', array() ) );
$jp['reprint_exporter']     = class_exists( '\Automattic\Jetpack\Reprint_Export\Reprint_Exporter' ) ? (bool) \Automattic\Jetpack\Reprint_Export\Reprint_Exporter::is_available() : false;
$jp['related_plugins']      = array_values( array_filter( array_column( $out['plugins'], 'slug' ), function ( $s ) {
	return 0 === strpos( $s, 'jetpack' ) || in_array( $s, array( 'akismet', 'vaultpress', 'zero-bs-crm', 'wpcomsh' ), true );
} ) );
$jp_plan                    = get_option( 'jetpack_active_plan' );
$jp['plan_slug']            = is_array( $jp_plan ) && isset( $jp_plan['product_slug'] ) ? $jp_plan['product_slug'] : null;
$jp['plan_class']           = is_array( $jp_plan ) && isset( $jp_plan['class'] ) ? $jp_plan['class'] : null;
$jp_products                = get_option( 'jetpack_site_products' );
$jp['product_slugs']        = is_array( $jp_products ) ? array_values( array_filter( array_map( function ( $p ) {
	return is_array( $p ) && isset( $p['product_slug'] ) ? $p['product_slug'] : null;
}, $jp_products ) ) ) : array();
$jp['boost_active']         = is_plugin_active( 'jetpack-boost/jetpack-boost.php' );
$jp['social_plugin_active'] = is_plugin_active( 'jetpack-social/jetpack-social.php' );
$jp['social_connections']   = (int) $wpdb->get_var( "SELECT COUNT(*) FROM {$wpdb->options} WHERE option_name = 'jetpack_publicize_connections' AND option_value NOT IN ('', 'a:0:{}')" );
$jp['crm_active']           = is_plugin_active( 'zero-bs-crm/ZeroBSCRM.php' );
$jp['search_plugin_active'] = is_plugin_active( 'jetpack-search/jetpack-search.php' );
$out['jetpack']             = $jp;

/* ---------- Jetpack payments: donations, paid content, payment buttons ---------- */
$jp_pay_like = array( '%wp:jetpack/donations%', '%wp:jetpack/recurring-payments%', '%wp:jetpack/payment-buttons%', '%wp:premium-content/%', '%wp:jetpack/paywall%', '%wp:jetpack/paid-content%' );
$out['jetpack_payments'] = array(
	'plans'             => (int) $wpdb->get_var( "SELECT COUNT(*) FROM {$wpdb->posts} WHERE post_type = 'jp_mem_plan' AND post_status = 'publish'" ),
	'posts_with_blocks' => (int) $wpdb->get_var( $wpdb->prepare( "SELECT COUNT(*) FROM {$wpdb->posts} WHERE post_status NOT IN ('trash','auto-draft','inherit') AND post_type <> 'revision' AND (post_content LIKE %s OR post_content LIKE %s OR post_content LIKE %s OR post_content LIKE %s OR post_content LIKE %s OR post_content LIKE %s)", $jp_pay_like ) ),
);

/* ---------- VideoPress ---------- */
$like              = function ( $needle ) use ( $wpdb ) {
	return '%' . $wpdb->esc_like( $needle ) . '%';
};
$content_where     = "post_status NOT IN ('trash','auto-draft','inherit') AND post_type NOT IN ('revision')";
$vp                = array(
	'module_active'        => in_array( 'videopress', $jp['active_modules'], true ),
	'plugin_active'        => is_plugin_active( 'jetpack-videopress/jetpack-videopress.php' ),
	'attachments_with_guid' => $count( "SELECT COUNT(DISTINCT post_id) FROM {$wpdb->postmeta} WHERE meta_key = 'videopress_guid' AND meta_value <> ''" ),
	'video_attachments'    => $count( "SELECT COUNT(*) FROM {$wpdb->posts} WHERE post_type = 'attachment' AND post_mime_type LIKE 'video/%'" ),
	'posts_with_block'     => $count( $wpdb->prepare( "SELECT COUNT(*) FROM {$wpdb->posts} WHERE {$content_where} AND post_content LIKE %s", $like( 'wp:videopress/video' ) ) ),
	'posts_with_shortcode' => $count( $wpdb->prepare( "SELECT COUNT(*) FROM {$wpdb->posts} WHERE {$content_where} AND (post_content LIKE %s OR post_content LIKE %s)", $like( '[videopress ' ), $like( '[wpvideo ' ) ) ),
	'posts_with_embed_url' => $count( $wpdb->prepare( "SELECT COUNT(*) FROM {$wpdb->posts} WHERE {$content_where} AND (post_content LIKE %s OR post_content LIKE %s OR post_content LIKE %s)", $like( 'videopress.com/v/' ), $like( 'videopress.com/embed/' ), $like( 'video.wordpress.com/embed/' ) ) ),
	'posts_with_videos_files_url' => $count( $wpdb->prepare( "SELECT COUNT(*) FROM {$wpdb->posts} WHERE {$content_where} AND post_content LIKE %s", $like( 'videos.files.wordpress.com' ) ) ),
);
$vp['in_use']      = (bool) ( $vp['attachments_with_guid'] || $vp['posts_with_block'] || $vp['posts_with_shortcode'] || $vp['posts_with_embed_url'] || $vp['posts_with_videos_files_url'] );
$vp['videos'] = $wpdb->get_results( "SELECT p.ID AS id, p.post_title AS title, m.meta_value AS guid FROM {$wpdb->postmeta} m JOIN {$wpdb->posts} p ON p.ID = m.post_id WHERE m.meta_key = 'videopress_guid' AND m.meta_value <> '' ORDER BY p.ID LIMIT 300", ARRAY_A );
$vp['theme_files'] = array();
$out['videopress'] = $vp;

/* ---------- Content and write activity ---------- */
$since30            = gmdate( 'Y-m-d H:i:s', time() - 30 * DAY_IN_SECONDS );
$users              = count_users();
$out['content']     = array(
	'post_types'            => $wpdb->get_results( "SELECT post_type, COUNT(*) AS n FROM {$wpdb->posts} WHERE post_status NOT IN ('auto-draft','trash') GROUP BY post_type ORDER BY n DESC LIMIT 40", ARRAY_A ),
	'max_post_id'           => $count( "SELECT MAX(ID) FROM {$wpdb->posts}" ),
	'posts_modified_30d'    => $count( $wpdb->prepare( "SELECT COUNT(*) FROM {$wpdb->posts} WHERE post_modified_gmt >= %s AND post_type NOT IN ('revision','scheduled-action','shop_order','shop_order_placehold')", $since30 ) ),
	'comments_total'        => $count( "SELECT COUNT(*) FROM {$wpdb->comments}" ),
	'comments_30d'          => $count( $wpdb->prepare( "SELECT COUNT(*) FROM {$wpdb->comments} WHERE comment_date_gmt >= %s AND comment_type IN ('', 'comment')", $since30 ) ),
	'default_comment_status' => get_option( 'default_comment_status' ),
	'users_can_register'    => (bool) get_option( 'users_can_register' ),
	'users_total'           => $users['total_users'],
	'users_by_role'         => $users['avail_roles'],
	'users_registered_30d'  => $count( $wpdb->prepare( "SELECT COUNT(*) FROM {$wpdb->users} WHERE user_registered >= %s", $since30 ) ),
	'application_password_users' => $count( "SELECT COUNT(DISTINCT user_id) FROM {$wpdb->usermeta} WHERE meta_key = '_application_passwords' AND meta_value NOT IN ('', 'a:0:{}')" ),
);

/* Plugins that store visitor-created data locally. */
$write_tables = array(
	'formidable'      => array( $wpdb->prefix . 'frm_items', 'created_at' ),
	'gravityforms'    => array( $wpdb->prefix . 'gf_entry', 'date_created' ),
	'wpforms'         => array( $wpdb->prefix . 'wpforms_entries', 'date' ),
	'ninja-forms'     => array( $wpdb->prefix . 'nf3_objects', null ),
	'fluentform'      => array( $wpdb->prefix . 'fluentform_submissions', 'created_at' ),
	'jetpack-crm'     => array( $wpdb->prefix . 'zbs_contacts', null ),
	'jetpack-forms'   => array( null, null ),
	'wc-bookings'     => array( null, null ),
	'memberpress'     => array( $wpdb->prefix . 'mepr_transactions', 'created_at' ),
	'pmpro'           => array( $wpdb->prefix . 'pmpro_memberships_users', 'startdate' ),
	'learndash'       => array( $wpdb->prefix . 'learndash_user_activity', null ),
	'sensei'          => array( $wpdb->prefix . 'sensei_lms_progress', null ),
	'slicewp'         => array( $wpdb->prefix . 'slicewp_commissions', 'date_created' ),
	'affiliates-manager' => array( $wpdb->prefix . 'wpam_transactions', null ),
	'give'            => array( $wpdb->prefix . 'give_donors', null ),
	'mailpoet'        => array( $wpdb->prefix . 'mailpoet_subscribers', 'created_at' ),
	'events-tickets'  => array( $wpdb->prefix . 'tec_occurrences', null ),
);
$out['local_data'] = array();
foreach ( $write_tables as $key => $def ) {
	list( $table, $date_col ) = $def;
	if ( null === $table || ! $table_exists( $table ) ) {
		continue;
	}
	$row = array( 'key' => $key, 'table' => $table, 'rows' => $count( "SELECT COUNT(*) FROM `{$table}`" ) );
	if ( $date_col ) {
		$row['rows_30d'] = $count( $wpdb->prepare( "SELECT COUNT(*) FROM `{$table}` WHERE `{$date_col}` >= %s", $since30 ) );
	}
	$out['local_data'][] = $row;
}
$out['content']['feedback_posts_30d'] = $count( $wpdb->prepare( "SELECT COUNT(*) FROM {$wpdb->posts} WHERE post_type IN ('feedback','flamingo_inbound','wc_booking') AND post_date_gmt >= %s", $since30 ) );

/* ---------- WooCommerce ---------- */
$woo = array( 'active' => class_exists( 'WooCommerce' ) );
if ( $woo['active'] ) {
	$woo['version'] = defined( 'WC_VERSION' ) ? WC_VERSION : null;
	$woo['hpos']    = 'yes' === get_option( 'woocommerce_custom_orders_table_enabled' );
	$woo['hpos_sync'] = 'yes' === get_option( 'woocommerce_custom_orders_table_data_sync_enabled' );
	$woo['coming_soon'] = get_option( 'woocommerce_coming_soon' );
	$woo['currency']  = get_option( 'woocommerce_currency' );
	$woo['taxes']     = 'yes' === get_option( 'woocommerce_calc_taxes' );
	$woo['email_from'] = get_option( 'woocommerce_email_from_address' );

	$gateways = array();
	if ( function_exists( 'WC' ) && WC()->payment_gateways() ) {
		foreach ( WC()->payment_gateways()->payment_gateways() as $gw ) {
			if ( 'yes' === $gw->enabled ) {
				$gateways[] = array( 'id' => $gw->id, 'title' => wp_strip_all_tags( (string) $gw->get_method_title() ), 'class' => get_class( $gw ) );
			}
		}
	}
	$woo['gateways_enabled'] = $gateways;

	$orders_table = $wpdb->prefix . 'wc_orders';
	if ( $woo['hpos'] && $table_exists( $orders_table ) ) {
		$woo['orders_total']  = $count( "SELECT COUNT(*) FROM `{$orders_table}` WHERE type = 'shop_order'" );
		$woo['max_order_id']  = $count( "SELECT MAX(id) FROM `{$orders_table}`" );
		$woo['orders_30d']    = $count( $wpdb->prepare( "SELECT COUNT(*) FROM `{$orders_table}` WHERE type = 'shop_order' AND date_created_gmt >= %s", $since30 ) );
		$woo['orders_7d']     = $count( $wpdb->prepare( "SELECT COUNT(*) FROM `{$orders_table}` WHERE type = 'shop_order' AND date_created_gmt >= %s", gmdate( 'Y-m-d H:i:s', time() - 7 * DAY_IN_SECONDS ) ) );
		$woo['last_order_gmt'] = $wpdb->get_var( "SELECT MAX(date_created_gmt) FROM `{$orders_table}` WHERE type = 'shop_order'" );
		$woo['orders_by_utc_hour_30d'] = $wpdb->get_results( $wpdb->prepare( "SELECT HOUR(date_created_gmt) AS h, COUNT(*) AS n FROM `{$orders_table}` WHERE type = 'shop_order' AND date_created_gmt >= %s GROUP BY h ORDER BY h", $since30 ), ARRAY_A );
		$woo['orders_by_utc_weekday_30d'] = $wpdb->get_results( $wpdb->prepare( "SELECT DAYNAME(date_created_gmt) AS d, COUNT(*) AS n FROM `{$orders_table}` WHERE type = 'shop_order' AND date_created_gmt >= %s GROUP BY d", $since30 ), ARRAY_A );
	} else {
		$woo['orders_total']  = $count( "SELECT COUNT(*) FROM {$wpdb->posts} WHERE post_type = 'shop_order'" );
		$woo['max_order_id']  = $count( "SELECT MAX(ID) FROM {$wpdb->posts} WHERE post_type = 'shop_order'" );
		$woo['orders_30d']    = $count( $wpdb->prepare( "SELECT COUNT(*) FROM {$wpdb->posts} WHERE post_type = 'shop_order' AND post_date_gmt >= %s", $since30 ) );
		$woo['orders_7d']     = $count( $wpdb->prepare( "SELECT COUNT(*) FROM {$wpdb->posts} WHERE post_type = 'shop_order' AND post_date_gmt >= %s", gmdate( 'Y-m-d H:i:s', time() - 7 * DAY_IN_SECONDS ) ) );
		$woo['last_order_gmt'] = $wpdb->get_var( "SELECT MAX(post_date_gmt) FROM {$wpdb->posts} WHERE post_type = 'shop_order'" );
		$woo['orders_by_utc_hour_30d'] = $wpdb->get_results( $wpdb->prepare( "SELECT HOUR(post_date_gmt) AS h, COUNT(*) AS n FROM {$wpdb->posts} WHERE post_type = 'shop_order' AND post_date_gmt >= %s GROUP BY h ORDER BY h", $since30 ), ARRAY_A );
	}

	/* Webhooks: host and topic only. The secret and full URL stay on the site. */
	$woo['webhooks'] = array();
	if ( $table_exists( $wpdb->prefix . 'wc_webhooks' ) ) {
		foreach ( (array) $wpdb->get_results( "SELECT webhook_id, status, name, topic, delivery_url, failure_count FROM {$wpdb->prefix}wc_webhooks", ARRAY_A ) as $hook ) {
			$woo['webhooks'][] = array( 'id' => (int) $hook['webhook_id'], 'status' => $hook['status'], 'name' => $hook['name'], 'topic' => $hook['topic'], 'delivery_host' => wp_parse_url( $hook['delivery_url'], PHP_URL_HOST ), 'failures' => (int) $hook['failure_count'] );
		}
	}
	/* REST API keys: description, permissions and last use. Never the key. */
	$woo['api_keys'] = array();
	if ( $table_exists( $wpdb->prefix . 'woocommerce_api_keys' ) ) {
		$woo['api_keys'] = $wpdb->get_results( "SELECT key_id, user_id, description, permissions, last_access FROM {$wpdb->prefix}woocommerce_api_keys ORDER BY last_access DESC", ARRAY_A );
	}

	$wcpay = get_option( 'wcpay_account_data' );
	$wcpay_data = is_array( $wcpay ) && isset( $wcpay['data'] ) && is_array( $wcpay['data'] ) ? $wcpay['data'] : array();
	$wcpay_connected = null;
	if ( class_exists( 'WC_Payments' ) && method_exists( 'WC_Payments', 'get_account_service' ) ) {
		try {
			$wcpay_service   = WC_Payments::get_account_service();
			$wcpay_connected = $wcpay_service && method_exists( $wcpay_service, 'is_stripe_connected' ) ? (bool) $wcpay_service->is_stripe_connected() : null;
		} catch ( \Throwable $e ) {
			$wcpay_connected = null;
		}
	}
	$woo['woopayments'] = array(
		'plugin_active'  => is_plugin_active( 'woocommerce-payments/woocommerce-payments.php' ),
		'account_cached' => ! empty( $wcpay_data ),
		'connected'      => $wcpay_connected,
		'is_live'        => isset( $wcpay_data['is_live'] ) ? (bool) $wcpay_data['is_live'] : null,
		'status'         => isset( $wcpay_data['status'] ) ? $wcpay_data['status'] : null,
		'country'        => isset( $wcpay_data['country'] ) ? $wcpay_data['country'] : null,
		'test_mode'      => get_option( 'wcpay_test_mode' ),
		'saved_tokens'   => $table_exists( $wpdb->prefix . 'woocommerce_payment_tokens' ) ? $wpdb->get_results( "SELECT gateway_id, COUNT(*) AS n FROM {$wpdb->prefix}woocommerce_payment_tokens GROUP BY gateway_id", ARRAY_A ) : array(),
	);
	$helper = get_option( 'woocommerce_helper_data' );
	$woo['woocommerce_com_connected'] = is_array( $helper ) && ! empty( $helper['auth'] );

	$woo['subscriptions'] = array( 'plugin_active' => class_exists( 'WC_Subscriptions' ) );
	if ( $woo['subscriptions']['plugin_active'] ) {
		if ( $woo['hpos'] && $table_exists( $orders_table ) ) {
			$woo['subscriptions']['by_status'] = $wpdb->get_results( "SELECT status, COUNT(*) AS n FROM `{$orders_table}` WHERE type = 'shop_subscription' GROUP BY status", ARRAY_A );
		} else {
			$woo['subscriptions']['by_status'] = $wpdb->get_results( "SELECT post_status AS status, COUNT(*) AS n FROM {$wpdb->posts} WHERE post_type = 'shop_subscription' GROUP BY post_status", ARRAY_A );
		}
	}
	$woo['shipping_zones'] = $table_exists( $wpdb->prefix . 'woocommerce_shipping_zones' ) ? $count( "SELECT COUNT(*) FROM {$wpdb->prefix}woocommerce_shipping_zones" ) : null;
}
if ( $woo['active'] ) {
	/* Regulated goods change which gateways and hosts are allowed. Counted by name only. */
	$woo['regulated_product_terms'] = (int) $wpdb->get_var( "SELECT COUNT(*) FROM {$wpdb->posts} WHERE post_type = 'product' AND post_status = 'publish' AND post_title REGEXP '(^|[^a-z])(cbd|hemp|cannabi|thc|delta-?[89]|kratom|vape|e-?liquid|nicotine|tobacco|firearm|ammunition)'" );
}
$out['woocommerce'] = $woo;

/* ---------- Scheduled work ---------- */
$cron_hooks = array();
foreach ( (array) _get_cron_array() as $timestamp => $hooks ) {
	foreach ( (array) $hooks as $hook => $events ) {
		$cron_hooks[ $hook ] = isset( $cron_hooks[ $hook ] ) ? $cron_hooks[ $hook ] + count( $events ) : count( $events );
	}
}
ksort( $cron_hooks );
$out['cron'] = array( 'events' => array_sum( $cron_hooks ), 'hooks' => array_slice( $cron_hooks, 0, 150, true ), 'disable_wp_cron' => defined( 'DISABLE_WP_CRON' ) && DISABLE_WP_CRON );
if ( $table_exists( $wpdb->prefix . 'actionscheduler_actions' ) ) {
	$out['action_scheduler'] = array(
		'pending'     => $count( "SELECT COUNT(*) FROM {$wpdb->prefix}actionscheduler_actions WHERE status = 'pending'" ),
		'failed_30d'  => $count( $wpdb->prepare( "SELECT COUNT(*) FROM {$wpdb->prefix}actionscheduler_actions WHERE status = 'failed' AND scheduled_date_gmt >= %s", $since30 ) ),
		'pending_top' => $wpdb->get_results( "SELECT hook, COUNT(*) AS n FROM {$wpdb->prefix}actionscheduler_actions WHERE status = 'pending' GROUP BY hook ORDER BY n DESC LIMIT 20", ARRAY_A ),
	);
}

/* ---------- Integrations ---------- */
$core_namespaces = array( 'wp/v2', 'oembed/1.0', 'wp-site-health/v1', 'wp-block-editor/v1', 'wp-abilities/v1' );
$namespaces      = function_exists( 'rest_get_server' ) ? rest_get_server()->get_namespaces() : array();
$out['rest_namespaces'] = array_values( array_diff( $namespaces, $core_namespaces ) );

$smtp_plugins = array( 'wp-mail-smtp', 'post-smtp', 'easy-wp-smtp', 'fluent-smtp', 'mailgun', 'sendgrid-email-delivery-simplified', 'wp-ses', 'smtp-mailer', 'mailpoet' );
$active_slugs = array_column( array_filter( $out['plugins'], function ( $p ) {
	return $p['active'];
} ), 'slug' );
$out['mail'] = array( 'smtp_plugins_active' => array_values( array_intersect( $smtp_plugins, $active_slugs ) ) );

$snippet_plugins = array( 'my-custom-functions', 'code-snippets', 'insert-headers-and-footers', 'wpcode-premium', 'insert-php', 'header-footer-code-manager', 'custom-css-js', 'simple-custom-css-and-js', 'wp-headers-and-footers', 'woody-ad-snippets' );
$out['code_in_database'] = array( 'plugins_active' => array_values( array_intersect( $snippet_plugins, $active_slugs ) ), 'custom_css_posts' => $count( "SELECT COUNT(*) FROM {$wpdb->posts} WHERE post_type = 'custom_css' AND post_content <> ''" ) );

$out['redirects'] = array(
	'redirection_rows' => $table_exists( $wpdb->prefix . 'redirection_items' ) ? $count( "SELECT COUNT(*) FROM {$wpdb->prefix}redirection_items WHERE status = 'enabled'" ) : null,
	'yoast_premium'    => is_plugin_active( 'wordpress-seo-premium/wp-seo-premium.php' ),
	'rank_math_rows'   => $table_exists( $wpdb->prefix . 'rank_math_redirections' ) ? $count( "SELECT COUNT(*) FROM {$wpdb->prefix}rank_math_redirections" ) : null,
);

/* ---------- Team 51 tooling ---------- */
$out['team51'] = array(
	'atlantis_active'  => in_array( 'a8csp-atlantis', $active_slugs, true ),
	'atlantis_present' => in_array( 'a8csp-atlantis', array_column( $out['plugins'], 'slug' ), true ),
	'safety_net'       => in_array( 'safety-net', array_column( $out['plugins'], 'slug' ), true ) || in_array( 'safety-net', $out['mu_plugins']['dirs'], true ) || file_exists( WPMU_PLUGIN_DIR . '/safety-net.php' ),
	'sso_plugins'      => array_values( array_filter( array_column( $out['plugins'], 'slug' ), function ( $s ) {
		return false !== strpos( $s, 'force-jetpack-sso' );
	} ) ),
	'theme_mentions_atlantis' => null,
);
/* A theme that calls Atlantis (colophon, tracking) breaks when the plugin goes. */
$hits = 0;
foreach ( array_unique( array( get_stylesheet_directory(), get_template_directory() ) ) as $dir ) {
	$files = 0;
	$it    = new RecursiveIteratorIterator( new RecursiveDirectoryIterator( $dir, FilesystemIterator::SKIP_DOTS ) );
	foreach ( $it as $file ) {
		if ( ++$files > 4000 ) {
			break;
		}
		if ( ! preg_match( '/\.(php|html|json)$/', $file->getFilename() ) || $file->getSize() > 400000 || false !== strpos( $file->getPathname(), '/node_modules/' ) || false !== strpos( $file->getPathname(), '/vendor/' ) ) {
			continue;
		}
		$source = (string) @file_get_contents( $file->getPathname() );
		if ( preg_match( '/atlantis|a8csp|team51[_-]credits|colophon/i', $source ) ) {
			++$hits;
		}
		if ( preg_match( '/videopress\.com|videos\.files\.wordpress\.com|video\.wordpress\.com|wp:videopress|\[videopress /i', $source ) ) {
			$out['videopress']['theme_files'][] = str_replace( WP_CONTENT_DIR . '/', '', $file->getPathname() );
		}
	}
}
$out['team51']['theme_mentions_atlantis'] = $hits;

/* ---------- People with elevated access ---------- */
$out['privileged_users'] = array();
foreach ( get_users( array( 'role__in' => array( 'administrator', 'shop_manager' ), 'number' => 200, 'fields' => array( 'ID', 'user_login', 'user_email', 'user_registered' ) ) ) as $u ) {
	$out['privileged_users'][] = array( 'id' => (int) $u->ID, 'login' => $u->user_login, 'email' => $u->user_email, 'roles' => array_values( (array) get_userdata( $u->ID )->roles ), 'registered' => substr( $u->user_registered, 0, 10 ) );
}

/* ---------- Database ---------- */
$tables = $wpdb->get_results( $wpdb->prepare( 'SELECT table_name AS name, table_rows AS approx_rows, ROUND((data_length + index_length) / 1048576, 1) AS mb FROM information_schema.tables WHERE table_schema = %s ORDER BY (data_length + index_length) DESC', DB_NAME ), ARRAY_A );
$out['database'] = array(
	'tables'          => count( $tables ),
	'total_mb'        => round( array_sum( array_column( $tables, 'mb' ) ), 1 ),
	'largest'         => array_slice( $tables, 0, 12 ),
	'foreign_prefix'  => array_values( array_filter( array_column( $tables, 'name' ), function ( $n ) use ( $wpdb ) {
		return 0 !== strpos( $n, $wpdb->prefix );
	} ) ),
	'autoload_kb'     => round( (int) $wpdb->get_var( "SELECT SUM(LENGTH(option_value)) FROM {$wpdb->options} WHERE autoload IN ('yes','on','auto','auto-on')" ) / 1024 ),
	'charset'         => $wpdb->charset,
	'collate'         => $wpdb->collate,
);

/* Uploads on disk: a quick du-style total is too slow on big sites, so sample the year folders. */
$upload = wp_get_upload_dir();
$out['uploads'] = array( 'basedir' => $upload['basedir'], 'attachments' => $count( "SELECT COUNT(*) FROM {$wpdb->posts} WHERE post_type = 'attachment'" ), 'top_level' => array_values( array_map( 'basename', (array) glob( $upload['basedir'] . '/*', GLOB_ONLYDIR ) ) ) );

t51_emit( $out );
