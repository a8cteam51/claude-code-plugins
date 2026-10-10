<?php
/**
 * Read-only: md5 of every file under the given wp-content paths.
 *
 * Arguments ($t51_args): { "paths": ["themes/my-theme", "mu-plugins/mu-loader.php"] }
 * Used by `deploy_check.py drift` to compare a server against a git revision.
 */

$paths  = isset( $t51_args['paths'] ) ? (array) $t51_args['paths'] : array();
$hashes = array();
$notes  = array();
$limit  = 8000;

foreach ( $paths as $rel ) {
	$rel = trim( str_replace( '..', '', (string) $rel ), '/' );
	$abs = WP_CONTENT_DIR . '/' . $rel;
	if ( is_file( $abs ) ) {
		$hashes[ $rel ] = md5_file( $abs );
		continue;
	}
	if ( ! is_dir( $abs ) ) {
		$notes[] = 'missing: ' . $rel;
		continue;
	}
	$it = new RecursiveIteratorIterator( new RecursiveDirectoryIterator( $abs, FilesystemIterator::SKIP_DOTS ) );
	foreach ( $it as $file ) {
		$path = $file->getPathname();
		if ( ! $file->isFile() || false !== strpos( $path, '/node_modules/' ) || false !== strpos( $path, '/.git/' ) ) {
			continue;
		}
		if ( count( $hashes ) >= $limit ) {
			$notes[] = 'stopped at ' . $limit . ' files';
			break 2;
		}
		$key            = $rel . substr( $path, strlen( $abs ) );
		$hashes[ $key ] = $file->getSize() > 8 * 1048576 ? 'size:' . $file->getSize() : md5_file( $path );
	}
}

t51_emit( array( 'hashes' => $hashes, 'notes' => $notes ) );
