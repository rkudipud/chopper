#!/usr/intel/bin/perl

$tab_space = 4 ;
open(FILE,$ARGV[0]) or die "-E- <$ARGV[0]> not found\n" ;
$indent = 0 ;
foreach $line (<FILE>) {
    chomp $line ;
    $line =~ s/^\s+// ;
#    next if ( $line eq "" ) ;
    $flag = 0 ;
    $space = "" ;
    $char  = "" ;
    $orig_indent = $indent ;
    $prev = "";
    for ( $i = 0 ; $i < length($line) ; $i++ ) {
        $prev_prev = $prev;
        $prev = $char ;
        $char = substr($line,$i,1) ;
        #last if ( $char eq "#" && $prev ne "\\") ;
        if ( $char eq "{" && $prev ne "\\" ) {
            $indent++ ;
            if ( $flag == 0 ) { $flag-- ; }
        } elsif ( $char eq "}" && ($prev ne "\\" || ($prev eq "\\" && $prev_prev eq "\\"))) {
            $indent-- ;
            if ( $flag == 0 ) { $flag++ ; }
        }
    }
    if ( $flag == 1 ) {
        for ( $s = 0 ; $s < ($tab_space * ($orig_indent - 1)) ; $s++ ) {
            $space .= " " ;
        }
    } else {
        if ($line =~ /^\s*((topology|interface|constraint|action):|end|pattern\s+\S+)\s*$/) {
            for ( $s = 0 ; $s < ($tab_space * $orig_indent - ($tab_space/2)) ; $s++ ) {
                $space .= " " ;
            }
        } else {
            for ( $s = 0 ; $s < ($tab_space * $orig_indent) ; $s++ ) {
                $space .= " " ;
            }
        }
    }
    print "${space}$line\n" ;
}
close FILE ;

