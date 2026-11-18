<?php
/**
 * Install, remove or report on one of this plugin's migration mu-plugins.
 *
 * Arguments ($t51_args): { "action": "install|remove|status", "name": "t51-migration-*.php",
 *                          "content_b64": "...", "replace": { "__TOKEN__": "value" } }
 *
 * WRITES TO THE SITE when action is install or remove. Only files named
 * t51-migration-*.php directly inside the mu-plugins directory are touched.
 */

$action = isset( $t51_args['action'] ) ? $t51_args['action'] : 'status';
$name   = isset( $t51_args['name'] ) ? basename( (string) $t51_args['name'] ) : '';
$result = array( 'action' => $action, 'name' => $name, 'ok' => false );

if ( ! preg_match( '/^t51-migration-[a-z0-9-]+\.php$/', $name ) ) {
	$result['error'] = 'refused: name must match t51-migration-*.php';
} else {
	$path             = WPMU_PLUGIN_DIR . '/' . $name;
	$result['path']   = $path;
	$result['home']   = home_url();
	if ( 'install' === $action ) {
		$content = base64_decode( isset( $t51_args['content_b64'] ) ? $t51_args['content_b64'] : '', true );
		foreach ( (array) ( isset( $t51_args['replace'] ) ? $t51_args['replace'] : array() ) as $token => $value ) {
			$content = str_replace( $token, $value, $content );
		}
		if ( ! $content || 0 !== strpos( $content, '<?php' ) ) {
			$result['error'] = 'refused: content is empty or not PHP';
		} else {
			if ( ! is_dir( WPMU_PLUGIN_DIR ) ) {
				wp_mkdir_p( WPMU_PLUGIN_DIR );
			}
			$result['ok'] = false !== file_put_contents( $path, $content );
			if ( function_exists( 'opcache_invalidate' ) ) {
				@opcache_invalidate( $path, true );
			}
		}
	} elseif ( 'remove' === $action ) {
		$result['ok'] = file_exists( $path ) ? unlink( $path ) : true;
		if ( function_exists( 'opcache_invalidate' ) ) {
			@opcache_invalidate( $path, true );
		}
	} else {
		$result['ok'] = true;
	}
	clearstatcache();
	$result['present'] = file_exists( $path );
	if ( $result['present'] ) {
		$result['bytes']    = filesize( $path );
		$result['modified'] = gmdate( 'Y-m-d H:i:s', filemtime( $path ) );
		if ( preg_match( '/T51_FREEZE_MODE_DEFAULT\',\s*\'([a-z]+)\'/', (string) file_get_contents( $path ), $m ) ) {
			$result['mode'] = $m[1];
		}
	}
}

t51_emit( $result );
