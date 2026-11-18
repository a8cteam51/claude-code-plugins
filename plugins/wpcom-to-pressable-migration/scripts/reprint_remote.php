<?php
/**
 * Run the Reprint client on the Pressable TARGET, through `wp eval` (scripts/wp_eval.sh).
 *
 *   T51_ARGS='{"action":"probe"}' wp_eval.sh pressable <site> reprint_remote.php
 *
 * Actions (T51_ARGS.action):
 *   probe    Read-only. PHP, shell functions, extensions, writable places outside the web root,
 *            disk, table prefix, the shape of DB_HOST, and whether the last background test
 *            survived its SSH session.
 *   bgtest   Starts a two-minute background process that appends to a file, to see whether a
 *            process outlives the WP-CLI call. Writes only in the work directory.
 *   help     `php reprint.phar <command> --help`, for checking flags against the installed client.
 *   setup    Creates the work directory, downloads reprint.phar and runs `keygen` for the source.
 *            Prints the Migration Token (a public key) to paste into the source's Reprint screen.
 *   run      Runs `pull-files` or `pull-db`. On Pressable pass "foreground": true (a background process dies
 *            with the WP-CLI call); "max_seconds" caps it (default 1800). Resumable: run it again after a failure.
 *   status   Whether the background run is alive, its exit code and the end of its log.
 *   place    Copies the pulled wp-content into this site's wp-content, skipping platform files.
 *            Pass "dry_run": true first to see what it would write.
 *   sql      Runs one read-only SELECT against the imported tables (for checks after the pull).
 *   cleanup  Deletes the work directory: the private key, the state and the downloaded copy.
 *
 * setup, run, place and cleanup WRITE TO THE SITE. Everything is kept in one work directory
 * outside the web root (T51_ARGS.work, found by `probe`), never under /srv/htdocs.
 *
 * Secrets: the database password is read from this site's own constants and only ever written
 * to a 0600 script in the work directory; it is never printed. The private key never leaves the
 * work directory. Log tails are filtered for anything that looks like a credential.
 */

$args   = is_array( $t51_args ) ? $t51_args : array();
$action = isset( $args['action'] ) ? (string) $args['action'] : 'probe';
$work   = isset( $args['work'] ) ? rtrim( (string) $args['work'], '/' ) : '';
$out    = array( 'action' => $action, 'collected_at' => gmdate( 'c' ) );

$disabled = array_filter( array_map( 'trim', explode( ',', (string) ini_get( 'disable_functions' ) ) ) );
$can_run  = function ( $fn ) use ( $disabled ) {
	return function_exists( $fn ) && ! in_array( $fn, $disabled, true );
};
$sh       = function ( $cmd ) {
	$lines = array();
	$code  = 0;
	exec( $cmd . ' 2>&1', $lines, $code );
	return array( 'code' => $code, 'output' => implode( "\n", $lines ) );
};
$redact   = function ( $text ) {
	$text = preg_replace( '/(--(?:target-pass|mysql-password|secret)=)\S+/', '$1<redacted>', $text );
	return preg_replace( '/-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----/s', '<private key redacted>', $text );
};
$fail     = function ( $message ) use ( &$out ) {
	$out['error'] = $message;
	t51_emit( $out );
	exit;
};
$is_alive = function ( $pid ) use ( $can_run ) {
	if ( ! $pid ) {
		return false;
	}
	return $can_run( 'posix_kill' ) ? posix_kill( $pid, 0 ) : is_dir( "/proc/$pid" );
};
$inside_web_root = function ( $path ) {
	$roots = array( rtrim( ABSPATH, '/' ), rtrim( WP_CONTENT_DIR, '/' ), '/srv/htdocs' );
	foreach ( $roots as $root ) {
		if ( '' !== $root && ( $path === $root || 0 === strpos( $path . '/', $root . '/' ) ) ) {
			return true;
		}
	}
	return false;
};
$need_work = function () use ( $work, $inside_web_root, $fail ) {
	if ( '' === $work || '/' !== $work[0] ) {
		$fail( 'Pass "work": an absolute path outside the web root (probe lists candidates).' );
	}
	if ( $inside_web_root( $work ) ) {
		$fail( "Refusing $work: it is inside the web root, where the private key and the database download could be served." );
	}
};
$php    = defined( 'PHP_BINARY' ) && PHP_BINARY ? PHP_BINARY : 'php';
$phar   = $work . '/reprint.phar';
$state  = $work . '/state';
$files  = $work . '/files';
$key    = $work . '/reprint-key.pem';
$source = isset( $args['source'] ) ? (string) $args['source'] : '';

/* Where the pulled tree keeps wp-content: Reprint mirrors the source's absolute paths, so search for it. */
$find_content = function () use ( $files ) {
	if ( ! is_dir( $files ) ) {
		return null;
	}
	$it = new RecursiveIteratorIterator( new RecursiveDirectoryIterator( $files, FilesystemIterator::SKIP_DOTS ), RecursiveIteratorIterator::SELF_FIRST );
	$it->setMaxDepth( 5 );
	foreach ( $it as $path => $info ) {
		if ( $info->isDir() && 'wp-content' === $info->getFilename() && ( is_dir( "$path/themes" ) || is_dir( "$path/plugins" ) || is_dir( "$path/uploads" ) ) ) {
			return $path;
		}
	}
	return null;
};

switch ( $action ) {
	case 'probe':
		global $table_prefix;
		$candidates = array_unique( array_filter( array( getenv( 'HOME' ), sys_get_temp_dir(), '/tmp', dirname( rtrim( ABSPATH, '/' ) ), '/srv' ) ) );
		$places     = array();
		foreach ( $candidates as $dir ) {
			$places[] = array(
				'path'           => $dir,
				'exists'         => is_dir( $dir ),
				'writable'       => is_dir( $dir ) && is_writable( $dir ),
				'inside_webroot' => $inside_web_root( $dir ),
				'free_mb'        => is_dir( $dir ) ? (int) ( @disk_free_space( $dir ) / 1048576 ) : null, // phpcs:ignore
			);
		}
		$out    += array(
			'php_binary'      => $php,
			'php_version'     => PHP_VERSION,
			'sapi'            => PHP_SAPI,
			'shell_functions' => array_values( array_filter( array( 'exec', 'proc_open', 'shell_exec', 'passthru', 'popen' ), $can_run ) ),
			'extensions'      => array_values( array_filter( array( 'curl', 'openssl', 'zlib', 'json', 'mysqli', 'pdo_mysql', 'mbstring', 'phar', 'sodium', 'pcntl', 'posix' ), 'extension_loaded' ) ),
			'memory_limit'    => ini_get( 'memory_limit' ),
			'max_execution'   => ini_get( 'max_execution_time' ),
			'places'          => $places,
			'abspath'         => ABSPATH,
			'content_dir'     => WP_CONTENT_DIR,
			'table_prefix'    => $table_prefix,
			// The run needs to know whether this is a host, host:port or a socket. The host name is not a secret.
			'db_host'         => (string) DB_HOST,
			'is_pressable'    => defined( 'IS_PRESSABLE' ) && IS_PRESSABLE,
		);
		if ( '' !== $work ) {
			$out['work'] = array( 'path' => $work, 'exists' => is_dir( $work ), 'phar' => is_file( $phar ), 'key' => is_file( $key ), 'state' => is_dir( $state ) );
			$bg          = $work . '/bgtest.log';
			if ( is_file( $bg ) ) {
				$lines            = file( $bg, FILE_IGNORE_NEW_LINES );
				$out['bgtest']    = array( 'lines' => count( $lines ), 'first' => $lines[0] ?? null, 'last' => end( $lines ) ?: null, 'now' => gmdate( 'H:i:s' ) );
			}
		}
		break;

	case 'bgtest':
		$need_work();
		if ( ! $can_run( 'exec' ) ) {
			$fail( 'exec() is disabled for PHP CLI here; the background route cannot work. Use the laptop route.' );
		}
		wp_mkdir_p( $work );
		$bg  = $work . '/bgtest.log';
		$res = $sh( 'nohup sh -c ' . escapeshellarg( 'i=0; while [ $i -lt 60 ]; do date -u +%H:%M:%S >> ' . escapeshellarg( $bg ) . '; i=$((i+1)); sleep 2; done' ) . ' > /dev/null 2>&1 & echo $!' );
		$out += array( 'pid' => trim( $res['output'] ), 'log' => $bg, 'next' => 'Probe again in a minute with the same "work": if bgtest.last keeps moving after this call ended, background runs survive.' );
		break;

	case 'help':
		$need_work();
		$command = isset( $args['command'] ) ? preg_replace( '/[^a-z-]/', '', (string) $args['command'] ) : '';
		$res     = $sh( escapeshellarg( $php ) . ' ' . escapeshellarg( $phar ) . ( '' === $command ? ' --help' : ' ' . $command . ' --help' ) );
		$out    += array( 'code' => $res['code'], 'help' => $redact( $res['output'] ) );
		break;

	case 'setup':
		$need_work();
		if ( '' === $source ) {
			$fail( 'Pass "source": the live site address, e.g. https://example.com.' );
		}
		if ( ! wp_mkdir_p( $work ) || ! wp_mkdir_p( $state ) ) {
			$fail( "Could not create $work." );
		}
		@chmod( $work, 0700 ); // phpcs:ignore
		if ( ! is_file( $phar ) || ! empty( $args['refresh_phar'] ) ) {
			$url = isset( $args['phar_url'] ) ? (string) $args['phar_url'] : 'https://plugins.svn.wordpress.org/reprint/downloads/reprint.phar';
			$tmp = download_url( $url, 300 );
			if ( is_wp_error( $tmp ) ) {
				$fail( 'Downloading reprint.phar failed: ' . $tmp->get_error_message() );
			}
			rename( $tmp, $phar ); // phpcs:ignore
		}
		$version = $sh( escapeshellarg( $php ) . ' ' . escapeshellarg( $phar ) . ' --version' );
		$out    += array( 'reprint_version' => trim( $version['output'] ), 'phar_sha256' => hash_file( 'sha256', $phar ) );
		if ( ! is_file( $key ) ) {
			$res = $sh( escapeshellarg( $php ) . ' ' . escapeshellarg( $phar ) . ' keygen ' . escapeshellarg( $source ) . ' --state-dir=' . escapeshellarg( $state ) . ' --out=' . escapeshellarg( $key ) );
			@chmod( $key, 0600 ); // phpcs:ignore
			$out['keygen'] = array( 'code' => $res['code'], 'output' => $redact( $res['output'] ) );
		} else {
			$out['keygen'] = 'A key already exists in the work directory; its Migration Token was printed when it was made. Run cleanup to start over.';
		}
		break;

	case 'run':
		$need_work();
		$step = isset( $args['step'] ) ? (string) $args['step'] : '';
		if ( ! in_array( $step, array( 'files', 'db' ), true ) || '' === $source || empty( $args['new_site_url'] ) ) {
			$fail( 'Pass "step" (files or db), "source" and "new_site_url".' );
		}
		if ( ! is_file( $phar ) || ! is_file( $key ) ) {
			$fail( 'Run setup first.' );
		}
		if ( ! $can_run( 'exec' ) ) {
			$fail( 'exec() is disabled for PHP CLI here. Use the laptop route.' );
		}
		$pid_file = "$work/run-$step.pid";
		if ( is_file( $pid_file ) && $is_alive( (int) file_get_contents( $pid_file ) ) ) {
			$fail( "A $step run is still going (pid " . trim( file_get_contents( $pid_file ) ) . '). Check status.' );
		}
		$common = array(
			escapeshellarg( $php ),
			escapeshellarg( $phar ),
			'files' === $step ? 'pull-files' : 'pull-db',
			escapeshellarg( $source ),
			'--private-key-path=' . escapeshellarg( $key ),
			'--state-dir=' . escapeshellarg( $state ),
			'--new-site-url=' . escapeshellarg( (string) $args['new_site_url'] ),
			'--exclude-host-plugins',
			'--progress=jsonl',
		);
		if ( 'files' === $step ) {
			wp_mkdir_p( $files );
			$common[] = '--fs-root=' . escapeshellarg( $files );
			$common[] = '--include=:wp-content:';
			foreach ( (array) ( $args['exclude'] ?? array() ) as $path ) {
				$common[] = '--exclude=' . escapeshellarg( (string) $path );
			}
		} else {
			// host, host:port or host:/socket. A socket is not supported here yet.
			$host = (string) DB_HOST;
			$port = '3306';
			if ( false !== strpos( $host, ':/' ) ) {
				$fail( 'DB_HOST is a socket; pass the socket to Reprint by hand (see `help pull-db`).' );
			}
			if ( preg_match( '/^(.+):(\d+)$/', $host, $m ) ) {
				$host = $m[1];
				$port = $m[2];
			}
			$common = array_merge(
				$common,
				array(
					'--fs-root=' . escapeshellarg( $files ),
					'--target-engine=mysql',
					'--target-host=' . escapeshellarg( $host ),
					'--target-port=' . escapeshellarg( $port ),
					'--target-db=' . escapeshellarg( DB_NAME ),
					'--target-user=' . escapeshellarg( DB_USER ),
					'--target-pass=' . escapeshellarg( DB_PASSWORD ),
				)
			);
		}
		// The command, with the password, goes in a private script so it never appears in this output.
		$script = "$work/run-$step.sh";
		$log    = "$work/run-$step.log";
		$exit   = "$work/run-$step.exit";
		@unlink( $exit ); // phpcs:ignore
		file_put_contents( $script, "#!/bin/sh\n" . implode( ' ', $common ) . "\necho \$? > " . escapeshellarg( $exit ) . "\n" ); // phpcs:ignore
		chmod( $script, 0700 ); // phpcs:ignore
		if ( empty( $args['foreground'] ) ) {
			$res = $sh( 'nohup sh ' . escapeshellarg( $script ) . ' >> ' . escapeshellarg( $log ) . ' 2>&1 & echo $!' );
			file_put_contents( $pid_file, trim( $res['output'] ) ); // phpcs:ignore
			$out += array( 'step' => $step, 'pid' => trim( $res['output'] ), 'log' => $log, 'next' => 'Check with action=status.' );
			break;
		}
		// Pressable runs each WP-CLI call in its own container, so a background process dies with the call (2026-11-17).
		// Run in the foreground instead, capped so a hung pull cannot hold the call open; Reprint resumes on the next run.
		$max     = max( 60, (int) ( $args['max_seconds'] ?? 1800 ) );
		$started = microtime( true );
		$res     = $sh( 'timeout ' . $max . ' sh ' . escapeshellarg( $script ) . ' >> ' . escapeshellarg( $log ) . ' 2>&1; echo $?' );
		$code    = (int) trim( substr( $res['output'], strrpos( "\n" . $res['output'], "\n" ) ) );
		$lines   = is_file( $log ) ? file( $log, FILE_IGNORE_NEW_LINES ) : array();
		// Pressable's object cache keeps serving the pre-import options until flushed (2026-11-17).
		if ( 'db' === $step && 0 === $code ) {
			$out['cache_flushed'] = wp_cache_flush();
		}
		$out    += array(
			'step'     => $step,
			'exit'     => $code,
			'seconds'  => (int) ( microtime( true ) - $started ),
			'timed_out' => 124 === $code,
			'tail'     => $redact( implode( "\n", array_slice( $lines, -15 ) ) ),
			'next'     => 0 === $code ? 'Done.' : ( 124 === $code ? 'Cut off at max_seconds: run the same command again to resume.' : 'Failed: read the tail, then run again to resume.' ),
		);
		break;

	case 'status':
		$need_work();
		foreach ( array( 'files', 'db' ) as $step ) {
			$log = "$work/run-$step.log";
			if ( ! is_file( $log ) ) {
				continue;
			}
			$pid   = is_file( "$work/run-$step.pid" ) ? (int) file_get_contents( "$work/run-$step.pid" ) : 0;
			$alive = $is_alive( $pid );
			$lines = file( $log, FILE_IGNORE_NEW_LINES );
			$tail  = array_slice( $lines, -1 * (int) ( $args['lines'] ?? 25 ) );
			// The last JSONL progress line, decoded, is the clearest single summary.
			$last = null;
			for ( $i = count( $lines ) - 1; $i >= 0 && null === $last; $i-- ) {
				$decoded = json_decode( $lines[ $i ], true );
				$last    = is_array( $decoded ) ? $decoded : null;
			}
			$out[ $step ] = array(
				'pid'      => $pid,
				'alive'    => $alive,
				'exit'     => is_file( "$work/run-$step.exit" ) ? (int) trim( file_get_contents( "$work/run-$step.exit" ) ) : null,
				'last'     => $last,
				'tail'     => $redact( implode( "\n", $tail ) ),
				'log_size' => filesize( $log ),
			);
		}
		$content = $find_content();
		if ( $content ) {
			$out['pulled_wp_content'] = $content;
		}
		break;

	case 'place':
		$need_work();
		$from = $find_content();
		if ( ! $from ) {
			$fail( 'No pulled wp-content found under the work directory. Run the files step first.' );
		}
		$to = rtrim( WP_CONTENT_DIR, '/' );
		// Never copied: platform files of either host, caches, and the migration's own mu-plugins.
		$skip = array_merge(
			array( 'object-cache.php', 'advanced-cache.php', 'db.php', 'db-error.php', 'cache', 'boost-cache', 'upgrade', 'upgrade-temp-backup', 'jetpack-waf', 'mu-plugins/wpcomsh', 'mu-plugins/wpcomsh-loader.php', 'mu-plugins/woocommerce-fraud-protection', 'mu-plugins/woocommerce-fraud-protection-loader.php', 'mu-plugins/t51-migration-freeze.php', 'mu-plugins/t51-migration-quarantine.php' ),
			(array) ( $args['skip'] ?? array() )
		);
		$dry     = ! empty( $args['dry_run'] );
		$written = 0;
		$same    = 0;
		$over    = array();
		$top     = array();
		$links   = array();
		$it      = new RecursiveIteratorIterator( new RecursiveDirectoryIterator( $from, FilesystemIterator::SKIP_DOTS ), RecursiveIteratorIterator::SELF_FIRST );
		foreach ( $it as $path => $info ) {
			$rel = substr( $path, strlen( $from ) + 1 );
			foreach ( $skip as $s ) {
				if ( $rel === $s || 0 === strpos( $rel, $s . '/' ) ) {
					continue 2;
				}
			}
			// Atomic links its platform plugins (Jetpack, Akismet, Gutenberg...) into wp-content; rehearse.plugins installs them.
			if ( $info->isLink() ) {
				$links[] = $rel;
				continue;
			}
			$dest = "$to/$rel";
			if ( $info->isDir() ) {
				$dry || wp_mkdir_p( $dest );
				continue;
			}
			$first         = explode( '/', $rel )[0];
			$top[ $first ] = ( $top[ $first ] ?? 0 ) + 1;
			if ( is_file( $dest ) ) {
				if ( filesize( $dest ) === $info->getSize() && hash_file( 'md5', $dest ) === hash_file( 'md5', $path ) ) {
					++$same;
					continue;
				}
				if ( count( $over ) < 50 ) {
					$over[] = $rel;
				}
			}
			if ( ! $dry ) {
				wp_mkdir_p( dirname( $dest ) );
				if ( ! copy( $path, $dest ) ) {
					$fail( "Copy failed at $rel after $written files." );
				}
			}
			++$written;
		}
		$out += array( 'from' => $from, 'to' => $to, 'dry_run' => $dry, 'would_write' => $written, 'unchanged' => $same, 'overwrites' => $over, 'by_top_level' => $top, 'skipped' => $skip, 'symlinks_skipped' => $links );
		break;

	case 'sql':
		global $wpdb;
		$query = isset( $args['query'] ) ? trim( (string) $args['query'] ) : '';
		if ( ! preg_match( '/^(SELECT|SHOW)\s/i', $query ) || false !== strpos( $query, ';' ) ) {
			$fail( 'Only one SELECT or SHOW, without semicolons.' );
		}
		$out['rows']      = $wpdb->get_results( $query, ARRAY_A ); // phpcs:ignore
		$out['sql_error'] = $wpdb->last_error ?: null;
		break;

	case 'cleanup':
		$need_work();
		if ( ! is_dir( $work ) ) {
			$out['removed'] = false;
			break;
		}
		$res            = $sh( 'rm -rf ' . escapeshellarg( $work ) );
		$out['removed'] = ! is_dir( $work );
		$out['code']    = $res['code'];
		break;

	default:
		$fail( "Unknown action $action." );
}

t51_emit( $out );
