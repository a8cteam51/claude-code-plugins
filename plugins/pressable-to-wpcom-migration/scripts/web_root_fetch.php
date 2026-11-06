<?php
/**
 * WRITES FILES on the site it runs on: downloads files from the source's public
 * URLs into the same paths here. Run on the target only, after a yes.
 *
 * How the paper PDFs reached the eagleman.com copy (2026-11-06): the folder is
 * outside wp-content, so the Migration Assistant does not copy it, and its
 * files are public on the source. A redirect is followed, so fetching an old
 * redirected path places the file it redirects to at that old path.
 *
 * Arguments ($t51_args):
 *   { "source": "https://example.org", "paths": ["papers/a.pdf", ...], "max": 200 }
 * `paths` come from `web_root_compare.py --fetch-out`. Relative to the web root.
 *
 *   T51_ARGS="$(cat fetch.json)" wp_eval.sh wpcom <target> web_root_fetch.php
 *
 * Never writes PHP or server config, never outside the web root, and never
 * over an existing file inside wp-content. Elsewhere it replaces a file only
 * when the download differs in size.
 */

require_once ABSPATH . 'wp-admin/includes/file.php'; // download_url()

$web_root = rtrim( dirname( WP_CONTENT_DIR ), '/' );
$source   = isset( $t51_args['source'] ) ? untrailingslashit( (string) $t51_args['source'] ) : '';
$paths    = isset( $t51_args['paths'] ) ? (array) $t51_args['paths'] : array();
$max      = isset( $t51_args['max'] ) ? (int) $t51_args['max'] : 200;
$out      = array( 'web_root' => $web_root, 'source' => $source, 'fetched' => array(), 'skipped' => array(), 'failed' => array() );

if ( ! preg_match( '#^https://#', $source ) || ! $paths ) {
	$out['error'] = 'Pass source (https://...) and paths.';
	t51_emit( $out );
	return;
}

$done = 0;
foreach ( $paths as $i => $rel ) {
	if ( $done >= $max ) {
		$out['remaining'] = array_slice( $paths, $i );
		break;
	}
	$rel = ltrim( (string) $rel, '/' );
	if ( '' === $rel || false !== strpos( $rel, '..' ) || preg_match( '#(^|/)\.(?!well-known/)|\.(php\d?|phtml|phar|htaccess|ini)$|^(__wp__|wp-admin|wp-includes)/#i', $rel ) ) {
		$out['skipped'][] = array( $rel, 'not allowed' );
		continue;
	}
	$abs        = $web_root . '/' . $rel;
	$in_content = 0 === strpos( $rel, 'wp-content/' );
	if ( $in_content && file_exists( $abs ) ) {
		$out['skipped'][] = array( $rel, 'exists in wp-content' );
		continue;
	}
	++$done;
	$tmp = download_url( $source . '/' . implode( '/', array_map( 'rawurlencode', explode( '/', $rel ) ) ), 300 );
	if ( is_wp_error( $tmp ) ) {
		$out['failed'][] = array( $rel, $tmp->get_error_message() );
		continue;
	}
	$bytes = (int) filesize( $tmp );
	if ( file_exists( $abs ) && (int) filesize( $abs ) === $bytes ) {
		$out['skipped'][] = array( $rel, 'same size' );
		@unlink( $tmp );
		continue;
	}
	if ( ! wp_mkdir_p( dirname( $abs ) ) || ! ( @rename( $tmp, $abs ) || ( @copy( $tmp, $abs ) && @unlink( $tmp ) ) ) ) {
		$out['failed'][] = array( $rel, 'could not write' );
		@unlink( $tmp );
		continue;
	}
	@chmod( $abs, 0644 );
	$out['fetched'][] = array( $rel, $bytes );
}

t51_emit( $out );
