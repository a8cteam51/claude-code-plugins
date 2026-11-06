<?php
/**
 * Read-only inventory of what a site serves from outside wp-content.
 *
 * The copy brings wp-content and the database only. Anything else in the web
 * root (folders of PDFs, verification files, .well-known) stays behind, and
 * links or redirects that point at it break. Found on eagleman.com, where the
 * theme moves PDFs tagged "papers" from uploads to /srv/htdocs/papers.
 *
 * Runs through scripts/wp_eval.sh like site_audit.php:
 *   wp_eval.sh pressable <site> web_root.php > webroot.json
 *
 * Collects:
 *   entries      everything in the web root that is not WordPress or the host's own,
 *                with each folder's files listed (path, bytes) up to 5000
 *   wp_content_root  repo and tooling files at the wp-content root (README, composer.json,
 *                dotfiles), which the copy carries over and serves publicly
 *   links        same-site links in content to files outside wp-content, by folder
 *   attachments  attachments whose file is not in uploads, and how many sit in the web root
 *   uploads      upload_path / upload_url_path / UPLOADS, if they move uploads
 *   redirects    redirect rules from static paths (WordPress.com serves those
 *                without WordPress) and rules into the web root
 *   code         lines in the theme and mu-plugins that build paths outside wp-content
 */

global $wpdb;

$web_root = rtrim( dirname( WP_CONTENT_DIR ), '/' );
$abspath  = rtrim( ABSPATH, '/' );
$out      = array( 'schema' => 1, 'collected_at' => gmdate( 'c' ), 'web_root' => $web_root, 'abspath' => ABSPATH );

/* ---------- Web root entries ---------- */
$standard = array( '.', '..', '.code-deployments', '.symlinks-bundle', '__wp__', 'wp-content', 'wp-config.php', 'wp-load.php', 'tmp', 'jetpack-temp', 'license.txt', 'readme.html',
	'index.php', 'xmlrpc.php', 'wp-activate.php', 'wp-blog-header.php', 'wp-comments-post.php', 'wp-config-sample.php', 'wp-cron.php',
	'wp-links-opml.php', 'wp-login.php', 'wp-mail.php', 'wp-settings.php', 'wp-signup.php', 'wp-trackback.php', 'wp-admin', 'wp-includes' );
$file_limit = 50000;
$list_limit = 5000; // files listed per folder, with sizes, for web_root_compare.py and web_root_fetch.php
$entries    = array();
foreach ( (array) @scandir( $web_root ) as $name ) {
	if ( in_array( $name, $standard, true ) ) {
		continue;
	}
	$path  = $web_root . '/' . $name;
	$entry = array( 'name' => $name, 'type' => is_dir( $path ) ? 'dir' : 'file' );
	if ( is_link( $path ) ) {
		$entry['link_to'] = (string) @readlink( $path );
	}
	if ( 'file' === $entry['type'] ) {
		$entry['bytes']    = (int) @filesize( $path );
		$entry['modified'] = gmdate( 'Y-m-d', (int) @filemtime( $path ) );
	} else {
		$files = 0;
		$bytes = 0;
		$newest = 0;
		$exts  = array();
		$list  = array();
		try {
			$it = new RecursiveIteratorIterator( new RecursiveDirectoryIterator( $path, FilesystemIterator::SKIP_DOTS ) );
			foreach ( $it as $f ) {
				if ( ! $f->isFile() ) {
					continue;
				}
				if ( ++$files > $file_limit ) {
					$entry['truncated'] = true;
					break;
				}
				$bytes += $f->getSize();
				$newest = max( $newest, $f->getMTime() );
				if ( count( $list ) < $list_limit ) {
					$list[] = array( substr( $f->getPathname(), strlen( $web_root ) + 1 ), $f->getSize() );
				}
				$ext    = strtolower( $f->getExtension() );
				$exts[ $ext ] = ( isset( $exts[ $ext ] ) ? $exts[ $ext ] : 0 ) + 1;
			}
		} catch ( Exception $e ) {
			$entry['error'] = $e->getMessage();
		}
		arsort( $exts );
		$entry += array( 'files' => min( $files, $file_limit ), 'bytes' => $bytes, 'modified' => $newest ? gmdate( 'Y-m-d', $newest ) : null, 'extensions' => array_slice( $exts, 0, 6, true ), 'list' => $list );
	}
	$entries[] = $entry;
}
$out['entries'] = $entries;

/* ---------- Repo and tooling files at the wp-content root ---------- */
// The copy brings everything in wp-content, so a README, composer.json or .git
// that a deploy left there is publicly readable on the new site too (eagleman.com).
$dropins = array( 'index.php', 'advanced-cache.php', 'object-cache.php', 'db.php', 'db-error.php', 'sunrise.php', 'maintenance.php',
	'fatal-error-handler.php', 'php-error.php', 'install.php', 'blog-deleted.php', 'blog-inactive.php', 'blog-suspended.php' );
$content_root = array();
foreach ( (array) @scandir( WP_CONTENT_DIR ) as $name ) {
	$path = WP_CONTENT_DIR . '/' . $name;
	if ( '.' === $name || '..' === $name || in_array( $name, $dropins, true ) ) {
		continue;
	}
	$is_dir = is_dir( $path );
	if ( $is_dir ? ( '.' === $name[0] || in_array( $name, array( 'node_modules', 'vendor', 'tests', 'bin' ), true ) )
		: preg_match( '/^(\.|readme|license|changelog|composer\.|package(-lock)?\.json|phpcs|phpunit|makefile|gulpfile|webpack|.*\.(md|ya?ml|lock|dist|sh|sql|log|bak|zip|gz))/i', $name ) ) {
		$content_root[] = array( 'name' => $name, 'type' => $is_dir ? 'dir' : 'file', 'bytes' => $is_dir ? null : (int) @filesize( $path ) );
	}
}
$out['wp_content_root'] = $content_root;

/* ---------- Same-site links in content to files outside wp-content ---------- */
$hosts = array();
foreach ( array( home_url(), site_url() ) as $u ) {
	$h = strtolower( (string) wp_parse_url( $u, PHP_URL_HOST ) );
	if ( $h ) {
		$hosts[] = preg_quote( $h, '#' );
		$hosts[] = preg_quote( 0 === strpos( $h, 'www.' ) ? substr( $h, 4 ) : 'www.' . $h, '#' );
	}
}
$exts_re  = 'pdf|docx?|xlsx?|pptx?|key|pages|numbers|rtf|odt|csv|txt|json|xml|zip|gz|tgz|rar|7z|dmg|exe|epub|mobi|mp3|m4a|wav|ogg|mp4|m4v|mov|webm|jpe?g|png|gif|webp|svg|ico|psd|ai|eps|ttf|otf|woff2?';
$link_re  = '#(?:href|src)\s*=\s*["\'](?:(?:https?:)?//(?:' . implode( '|', array_unique( $hosts ) ) . '))?(/[^"\'\s?\#<>]+\.(?:' . $exts_re . '))(?=["\'?\#])#i';
$by_dir   = array();
$scanned  = 0;
$post_cap = 50000;
$last_id  = 0;
while ( $scanned < $post_cap ) {
	$rows = $wpdb->get_results( $wpdb->prepare(
		"SELECT ID, post_content FROM {$wpdb->posts} WHERE ID > %d AND post_type NOT IN ('revision','attachment','customize_changeset','oembed_cache') AND post_status IN ('publish','private','future','draft','pending') AND post_content <> '' ORDER BY ID LIMIT 500",
		$last_id
	) );
	if ( ! $rows ) {
		break;
	}
	foreach ( $rows as $row ) {
		$last_id = (int) $row->ID;
		++$scanned;
		if ( ! preg_match_all( $link_re, $row->post_content, $m ) ) {
			continue;
		}
		foreach ( array_unique( $m[1] ) as $p ) {
			if ( preg_match( '#^/(wp-content|wp-includes|wp-admin)/#i', $p ) || 0 === strpos( $p, '//' ) ) {
				continue;
			}
			$parts = explode( '/', trim( $p, '/' ) );
			$dir   = count( $parts ) > 1 ? $parts[0] : '(root)';
			if ( ! isset( $by_dir[ $dir ] ) ) {
				$by_dir[ $dir ] = array( 'links' => 0, 'paths' => array(), 'in_web_root' => 0, 'posts' => array() );
			}
			if ( isset( $by_dir[ $dir ]['paths'][ $p ] ) ) {
				continue;
			}
			$by_dir[ $dir ]['paths'][ $p ] = file_exists( $web_root . rawurldecode( $p ) );
			$by_dir[ $dir ]['links']++;
			$by_dir[ $dir ]['in_web_root'] += $by_dir[ $dir ]['paths'][ $p ] ? 1 : 0;
			if ( count( $by_dir[ $dir ]['posts'] ) < 5 ) {
				$by_dir[ $dir ]['posts'][ $row->ID ] = true;
			}
		}
	}
}
$links = array();
foreach ( $by_dir as $dir => $info ) {
	$links[] = array(
		'dir'         => $dir,
		'files'       => $info['links'],
		'in_web_root' => $info['in_web_root'],
		'examples'    => array_slice( array_keys( $info['paths'] ), 0, 5 ),
		'missing_examples' => array_slice( array_keys( array_filter( $info['paths'], function ( $found ) {
			return ! $found;
		} ) ), 0, 5 ),
		'post_ids'    => array_keys( $info['posts'] ),
		// Every path that exists in the web root, so the copy can be checked file by file (verify.web-root).
		'paths'       => array_slice( array_keys( array_filter( $info['paths'] ) ), 0, 2000 ),
	);
}
usort( $links, function ( $a, $b ) {
	return $b['files'] - $a['files'];
} );
$out['links'] = array( 'posts_scanned' => $scanned, 'capped' => $scanned >= $post_cap, 'by_dir' => $links );

/* ---------- Attachments whose file is not in uploads ---------- */
$upload      = wp_get_upload_dir();
$basedir     = rtrim( $upload['basedir'], '/' );
$att_cap     = 20000;
$attached    = $wpdb->get_results( $wpdb->prepare( "SELECT post_id, meta_value FROM {$wpdb->postmeta} WHERE meta_key = '_wp_attached_file' ORDER BY post_id LIMIT %d", $att_cap ) );
$in_root     = array();
$missing     = array();
foreach ( $attached as $a ) {
	$rel = ltrim( (string) $a->meta_value, '/' );
	if ( '' === $rel || file_exists( 0 === strpos( $a->meta_value, '/' ) ? $a->meta_value : $basedir . '/' . $rel ) ) {
		continue;
	}
	if ( file_exists( $web_root . '/' . $rel ) ) {
		$in_root[] = $rel;
	} else {
		$missing[] = $rel;
	}
}
$out['attachments'] = array(
	'checked'          => count( $attached ),
	'total'            => (int) $wpdb->get_var( "SELECT COUNT(*) FROM {$wpdb->postmeta} WHERE meta_key = '_wp_attached_file'" ),
	'in_web_root'      => count( $in_root ),
	'in_web_root_dirs' => array_count_values( array_map( function ( $p ) {
		return false !== strpos( $p, '/' ) ? strtok( $p, '/' ) : '(root)';
	}, $in_root ) ),
	'in_web_root_examples' => array_slice( $in_root, 0, 5 ),
	'missing'          => count( $missing ),
	'missing_examples' => array_slice( $missing, 0, 5 ),
);

/* ---------- Upload location settings ---------- */
$out['uploads'] = array(
	'basedir'         => $upload['basedir'],
	'baseurl'         => $upload['baseurl'],
	'in_wp_content'   => 0 === strpos( $basedir . '/', rtrim( WP_CONTENT_DIR, '/' ) . '/' ),
	'upload_path'     => (string) get_option( 'upload_path' ),
	'upload_url_path' => (string) get_option( 'upload_url_path' ),
	'uploads_const'   => defined( 'UPLOADS' ) ? UPLOADS : null,
);

/* ---------- Redirect rules ---------- */
$static_re   = '#^/?(wp-content/|.*\.(' . $exts_re . ')$)#i';
$root_target = function ( $target ) use ( $hosts, $exts_re ) {
	$path = preg_replace( '#^(?:https?:)?//(?:' . implode( '|', array_unique( $hosts ) ) . ')#i', '', (string) $target );
	return '/' === substr( $path, 0, 1 ) && ! preg_match( '#^/(wp-content|wp-includes|wp-admin)/#i', $path ) && preg_match( '#\.(' . $exts_re . ')$#i', $path ) ? $path : null;
};
$rules = array();
if ( $wpdb->get_var( $wpdb->prepare( 'SHOW TABLES LIKE %s', $wpdb->prefix . 'redirection_items' ) ) === $wpdb->prefix . 'redirection_items' ) {
	foreach ( (array) $wpdb->get_results( "SELECT url, action_data FROM {$wpdb->prefix}redirection_items WHERE status = 'enabled' AND action_type = 'url'" ) as $r ) {
		$rules[] = array( 'redirection', $r->url, $r->action_data );
	}
}
foreach ( (array) $wpdb->get_results( "SELECT p.ID, m.meta_value AS src, t.meta_value AS dst FROM {$wpdb->posts} p JOIN {$wpdb->postmeta} m ON m.post_id = p.ID AND m.meta_key = '_redirect_rule_from' LEFT JOIN {$wpdb->postmeta} t ON t.post_id = p.ID AND t.meta_key = '_redirect_rule_to' WHERE p.post_type = 'redirect_rule' AND p.post_status = 'publish'" ) as $r ) {
	$rules[] = array( 'safe-redirect-manager', $r->src, $r->dst );
}
foreach ( (array) get_option( 'wpseo-premium-redirects-base', array() ) as $r ) {
	if ( is_array( $r ) && isset( $r['origin'], $r['url'] ) ) {
		$rules[] = array( 'yoast', '/' . ltrim( $r['origin'], '/' ), $r['url'] );
	}
}
$from_static = array();
$into_root   = array();
foreach ( $rules as $r ) {
	list( $plugin, $src, $dst ) = $r;
	if ( preg_match( $static_re, (string) $src ) ) {
		$from_static[] = array( $plugin, $src, $dst );
	}
	$p = $root_target( $dst );
	if ( $p ) {
		$parts = explode( '/', trim( $p, '/' ) );
		$into_root[] = count( $parts ) > 1 ? $parts[0] : '(root)';
	}
}
$out['redirects'] = array(
	'rules'                 => count( $rules ),
	'from_static'           => count( $from_static ),
	'from_static_examples'  => array_slice( array_map( function ( $r ) {
		return sprintf( '%s: %s -> %s', $r[0], $r[1], substr( (string) $r[2], 0, 160 ) );
	}, $from_static ), 0, 5 ),
	// Plain paths only (no regex rules), for url_check.py and for placing files at their old paths.
	'from_static_paths'     => array_slice( array_values( array_unique( array_filter( array_map( function ( $r ) {
		$src = '/' . ltrim( (string) wp_parse_url( (string) $r[1], PHP_URL_PATH ), '/' );
		return preg_match( '#[\^$*()\[\]+?\\\\]#', (string) $r[1] ) ? null : $src;
	}, $from_static ) ) ) ), 0, 2000 ),
	'into_web_root'         => array_count_values( $into_root ),
);

/* ---------- Code that builds paths outside wp-content ---------- */
$code_re = array(
	'#dirname\s*\(\s*WP_CONTENT_DIR\s*\)#',
	'#DOCUMENT_ROOT#',
	'#get_home_path\s*\(#',
	'#ABSPATH\s*\.\s*[\'"](?!/?(?:wp-(?:admin|includes|content|load|config|settings|blog-header|login|cron|mail|signup|activate|links-opml|trackback|comments-post)|xmlrpc\.php|index\.php))#',
);
$dirs  = array_unique( array( get_stylesheet_directory(), get_template_directory(), WPMU_PLUGIN_DIR ) );
$hits  = array();
$count = 0;
foreach ( $dirs as $dir ) {
	if ( ! is_dir( $dir ) ) {
		continue;
	}
	$it = new RecursiveIteratorIterator( new RecursiveCallbackFilterIterator(
		new RecursiveDirectoryIterator( $dir, FilesystemIterator::SKIP_DOTS ),
		function ( $f ) {
			return ! ( $f->isDir() && in_array( $f->getFilename(), array( 'vendor', 'node_modules', '.git' ), true ) );
		}
	) );
	foreach ( $it as $f ) {
		if ( 'php' !== strtolower( $f->getExtension() ) || $f->getSize() > 1048576 || ++$count > 4000 ) {
			continue;
		}
		foreach ( (array) @file( $f->getPathname() ) as $i => $line ) {
			foreach ( $code_re as $re ) {
				if ( preg_match( $re, $line ) ) {
					$hits[] = sprintf( '%s:%d: %s', substr( $f->getPathname(), strlen( WP_CONTENT_DIR ) + 1 ), $i + 1, substr( trim( $line ), 0, 160 ) );
					break;
				}
			}
			if ( count( $hits ) >= 40 ) {
				break 3;
			}
		}
	}
}
$out['code'] = array( 'dirs' => array_map( function ( $d ) {
	return substr( $d, strlen( WP_CONTENT_DIR ) + 1 );
}, $dirs ), 'hits' => $hits );

t51_emit( $out );
