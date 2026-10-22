<?php
/**
 * Read-only database fingerprints for db_diff.py. Run on the source and the
 * target; db_diff.py compares them to find rows that exist or changed on one
 * side only.
 *
 * Arguments ($t51_args):
 *   mode     "buckets" | "rows" | "fetch"
 *   hosts    host names to treat as equal, e.g. ["example.com", "example.wpcomstaging.com"]
 *   size     rows per bucket (buckets mode), default 1000
 *   tables   limit to these tables, without prefix (buckets mode, optional)
 *   want     rows mode:  { "<table without prefix>": [bucket numbers to list row by row], ... }
 *            fetch mode: { "<table without prefix>": [primary key values to return in full], ... }
 *
 * Every row is hashed in SQL after replacing each host with a token and
 * blanking the lengths in PHP-serialized strings, so the URL rewrite done by
 * the copy does not count as a change. Nothing is written.
 */

global $wpdb;
$mode   = isset( $t51_args['mode'] ) ? $t51_args['mode'] : 'buckets';
$hosts  = isset( $t51_args['hosts'] ) ? array_values( array_filter( (array) $t51_args['hosts'] ) ) : array();
$size   = max( 1, (int) ( isset( $t51_args['size'] ) ? $t51_args['size'] : 1000 ) );
$px     = $wpdb->prefix;
$wpdb->suppress_errors( true );

/* REGEXP_REPLACE needs MySQL 8 or MariaDB 10.0.5+. Without it serialized lengths are compared as they are. */
$has_regexp = '1' === (string) $wpdb->get_var( "SELECT REGEXP_REPLACE('s:12:\"', 's:[0-9]+:\"', '1') = '1'" );

$table_info = function ( $table ) use ( $wpdb ) {
	$cols = array();
	foreach ( (array) $wpdb->get_results( "SHOW COLUMNS FROM `{$table}`", ARRAY_A ) as $c ) {
		$cols[ $c['Field'] ] = $c['Type'];
	}
	$pk = array();
	foreach ( (array) $wpdb->get_results( "SHOW KEYS FROM `{$table}` WHERE Key_name = 'PRIMARY'", ARRAY_A ) as $k ) {
		$pk[ (int) $k['Seq_in_index'] ] = $k['Column_name'];
	}
	ksort( $pk );
	return array( 'cols' => $cols, 'pk' => array_values( $pk ) );
};

$row_hash = function ( $cols ) use ( $wpdb, $hosts, $has_regexp ) {
	$parts = array();
	foreach ( array_keys( $cols ) as $col ) {
		$expr = "IFNULL(CAST(`{$col}` AS CHAR), '\\\\N')";
		foreach ( $hosts as $h ) {
			$expr = 'REPLACE(' . $expr . ', ' . $wpdb->prepare( '%s', $h ) . ", '{h}')";
		}
		if ( $has_regexp ) {
			$expr = 'REGEXP_REPLACE(' . $expr . ", 's:[0-9]+:\"', 's:#:\"')";
		}
		$parts[] = $expr;
	}
	return 'MD5(CONCAT_WS(CHAR(31), ' . implode( ', ', $parts ) . '))';
};

/* A bucket groups rows by their first primary key column when it is numeric; otherwise the table is one bucket. */
$bucket_expr = function ( $info ) use ( $size ) {
	if ( $info['pk'] && preg_match( '/int|decimal/i', $info['cols'][ $info['pk'][0] ] ) ) {
		return 'FLOOR(`' . $info['pk'][0] . '` / ' . $size . ')';
	}
	return '0';
};
$key_expr = function ( $info ) {
	if ( ! $info['pk'] ) {
		return null;
	}
	return 'CONCAT_WS(CHAR(31), ' . implode( ', ', array_map( function ( $c ) { return "`{$c}`"; }, $info['pk'] ) ) . ')';
};

$out = array( 'mode' => $mode, 'prefix' => $px, 'regexp' => $has_regexp, 'collected_at' => gmdate( 'Y-m-d H:i:s' ) );

if ( 'buckets' === $mode ) {
	$only   = isset( $t51_args['tables'] ) ? (array) $t51_args['tables'] : null;
	$tables = array();
	foreach ( (array) $wpdb->get_col( $wpdb->prepare( 'SHOW TABLES LIKE %s', $wpdb->esc_like( $px ) . '%' ) ) as $table ) {
		$short = substr( $table, strlen( $px ) );
		if ( $only && ! in_array( $short, $only, true ) ) {
			continue;
		}
		$info  = $table_info( $table );
		$entry = array( 'pk' => $info['pk'], 'columns' => array_keys( $info['cols'] ), 'buckets' => array() );
		$hash  = $row_hash( $info['cols'] );
		$b     = $bucket_expr( $info );
		$rows  = $wpdb->get_results( "SELECT {$b} AS b, COUNT(*) AS n, LPAD(HEX(BIT_XOR(CAST(CONV(SUBSTRING({$hash}, 1, 16), 16, 10) AS UNSIGNED))), 16, '0') AS h FROM `{$table}` GROUP BY b", ARRAY_A );
		if ( null === $rows && $wpdb->last_error ) {
			$entry['error'] = $wpdb->last_error;
		}
		foreach ( (array) $rows as $r ) {
			$entry['buckets'][ (string) $r['b'] ] = array( (int) $r['n'], $r['h'] );
		}
		$tables[ $short ] = $entry;
	}
	$out['tables'] = $tables;
} elseif ( 'rows' === $mode || 'fetch' === $mode ) {
	/* One call covers every table, because each call through the CLI costs seconds. */
	$out['tables'] = array();
	foreach ( (array) $t51_args['want'] as $short => $wanted ) {
		$table = $px . preg_replace( '/[^A-Za-z0-9_]/', '', (string) $short );
		$info  = $table_info( $table );
		$key   = $key_expr( $info );
		$entry = array( 'pk' => $info['pk'], 'rows' => array() );
		if ( ! $key ) {
			$entry['error'] = 'no primary key';
		} elseif ( 'rows' === $mode ) {
			$b       = $bucket_expr( $info );
			$buckets = array_map( 'intval', (array) $wanted );
			$where   = '0' === $b ? '1=1' : "{$b} IN (" . implode( ',', $buckets ? $buckets : array( -1 ) ) . ')';
			$hash    = $row_hash( $info['cols'] );
			foreach ( (array) $wpdb->get_results( "SELECT {$key} AS k, SUBSTRING({$hash}, 1, 16) AS h FROM `{$table}` WHERE {$where}", ARRAY_A ) as $r ) {
				$entry['rows'][ 'k' . $r['k'] ] = $r['h']; /* Prefixed so PHP keeps it a map, not a list. */
			}
		} else {
			foreach ( array_chunk( (array) $wanted, 200 ) as $chunk ) {
				$in = implode( ',', array_map( function ( $k ) use ( $wpdb ) { return $wpdb->prepare( '%s', $k ); }, $chunk ) );
				foreach ( (array) $wpdb->get_results( "SELECT * FROM `{$table}` WHERE {$key} IN ({$in})", ARRAY_A ) as $r ) {
					$entry['rows'][] = $r;
				}
			}
		}
		$out['tables'][ $short ] = $entry;
	}
}

$wpdb->suppress_errors( false );
t51_emit( $out );
