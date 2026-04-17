#!/usr/bin/perl
# utils.pl — Mini domain Perl utility (file-level only, no proc extraction)

use strict;
use warnings;

sub helper_function {
    my ($arg) = @_;
    return uc($arg);
}

print helper_function("test"), "\n";
