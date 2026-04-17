#!/usr/intel/bin/perl5.40.1
####################################################################################################
####################################################################################################
#
#                                                                     
#
#
####################################################################################################


###########################################################
# fev_checker.pl
#
# This script creates the final violations XML for FEV.
###########################################################

##################
# Perl Libraries #
##################
use strict;
use warnings;
use v5.10;
use Cwd qw(abs_path);
use Getopt::Long;
use Data::Dumper;
use XML::LibXML;
use XML::Parser;
use File::Basename qw(basename dirname fileparse);
use XML::Writer;
use IO::File;

#use lib "$FindBin::RealBin/../lib/perl/";
# Used to determine if cth_query is defined and thus inside CTH environment
use File::Which;

BEGIN {
    my $cth_query_path = which 'cth_query';
    if (defined $cth_query_path && -e $cth_query_path) {
        # If cth_query path is defined (inside CTH environment) then use cth_query to determine path
        my $finale_path = `cth_query -resolve_path ToolVersion finale`; chomp($finale_path);
        unshift(@INC, "$finale_path/utils");
    }
    elsif (defined $ENV{FINALE_DIR}) {
        # Else if FINALE_DIR environment variable is defined then use that finale path
        unshift(@INC, "$ENV{FINALE_DIR}/utils");
    }
    else {
        # Else use hard-coded finale path
        unshift(@INC, "/p/hdk/pu_tu/prd/finale/23.01.001/utils");
    }
}

use ClosureCheckUtils;

# Capture the original command which was run. This variable needs to be set BEFORE any GetOptions call.
my $command_which_was_run = "$0 @ARGV";

#########
# Usage #
#########
sub usage {
  my($msg) = shift;
  print "$msg\n\n" if(defined $msg);

  print "fev_checker.pl --path <path> -B|--build_dir -fev_stages <all fev stages for merging> <directory> -outputfile <file>\n"
      . "               [-D|--design <block>] [-R|--run_dir <directory>] [-X|--tech <technology>]\n"
      . "               [-milestone <milestone>]\n"
      . "               [--nogreenstone_mode]\n"
      . "\n"
      . " This will generate FEV checks that are not based on indicators.\n"
      . "\n"
      . " Required:\n"
	  . "  --path <path>         Full path to the ward or workarea.\n"
      . "                         Expected directory structure underneath: --path/(runs|--source_dir)/-B/-X/-R/-O\n"
      . "                         See specific option explanations for details\n"
      . "  -B|--build_dir <dir>  Set design name & build directory that will be evaluated.\n"
      . "                         Defines design name and build directory under the --path\n"
      . "                         Provide a different design name with -D|--design.\n"
      . "  -outputfile <file>    Path to where the output file should be written.\n"
      . "  -fev_stages <stage>    List of fev stages run for merging (space separated list).\n"
      . "                         Example: -fev_stages \"fev_rtl2syn fev_syn2apr\"\n"
      . "\n"
      . " Optional:\n"
      . "  -D|--design <block>   Define a design name that is different than the -B|--build_dir\n"
      . "                         This does not change the -B directory under the ward, only the block name\n"
      . "                         Default: -B value\n"
      . "  -R|--run_dir <dir>    Define a different flow run directory under the ward\n"
      . "                         Default: 'fev_formality'\n"
      . "  -X|--tech <tech>      Specify technology layer to use.\n"
      . "                         Default: \$ENV{tech}\n"
      . "  -milestone <P05...>   Current milestone.\n"
      . "                         Milestone is accepted, but not used at this time, as there are no milestone specific checks.\n"
      . "\n"
      . "  --nogreenstone_mode   Specify this option if you are not using greenstone tool for waiving the violations.\n"
      . "  --debug     Print debug messages.\n"
      . "  --help      Prints this usage\n"
      . "\n";
  exit(1);
} # END sub usage

###############
# Get Options #
###############
my $debug = 0;
my $help  = 0;
my $opt_build_dir = "";
my $opt_design    = "";
my $opt_run_dir   = "";
my $flow_run_path   = "";
my $opt_path   = "";
my $opt_tech      = "";
my $opt_output_file = "";
my $fev_stage = "";
my $opt_milestone   = "";
my $opt_nogreenstone_mode = 0;

# Get all options
GetOptions("debug" => \$debug,
           "help"  => \$help,
           "path:s" => \$opt_path,
           "B|build_dir:s" => \$opt_build_dir,
           "D|design:s"    => \$opt_design,
           "R|run_dir:s"   => \$opt_run_dir,
           "X|tech:s"      => \$opt_tech,
           "outputfile:s"  => \$opt_output_file,
           "fev_stages:s"  => \$fev_stage,
           "milestone:s"   => \$opt_milestone,
           "nogreenstone_mode"   => \$opt_nogreenstone_mode,
          ) || usage();
usage() if($help);

usage("You must provide a build_dir.") if($opt_build_dir eq "");
$opt_path = $ENV{"ward"} if ($opt_path eq "");
$opt_design  = $opt_build_dir if($opt_design  eq "");
$opt_run_dir = "fev_formality"       if($opt_run_dir eq "");
$opt_tech    = $ENV{"tech"}   if($opt_tech    eq "");


my $dataObj  = Closure::Data->new();
$dataObj = Closure::Data->new(WARD    => $opt_path,
                              COMMAND => $command_which_was_run);

if($opt_tech eq "") {
	print "INTEL_ERROR : Cannot determine technology. Either provide -X,--tech or set env(tech).\n";
	exit(1);
}
if($opt_output_file eq "") {
	print "INTEL_ERROR : -outputfile is required.\n";
	exit(1);
}

if(!-d $opt_path) {
    print "INTEL_ERROR : --path '$opt_path' is not a valid directory. Cannot continue.\n";
    exit(1);
}

if($fev_stage eq "") {
	print "INTEL_ERROR : -fev_stages is required.\n";
	exit(1);
}
if($fev_stage =~ m/,/) {
	print "INTEL_ERROR : -fev_stages is a space separated list.\n";
    exit(1);
}

############
# Defaults #
############
my $script_loc = abs_path(dirname($0));

          ########
########### Main ##########
          ########

# Build paths to specific directories
#######################################

my $output_dir = dirname($opt_output_file);
`/usr/bin/mkdir -p $output_dir` if(!-d $output_dir);

if(!-d $output_dir || !-r $output_dir) {
    print "INTEL_ERROR : Cannot write output file to directory: $output_dir. Check permissions.";
    exit(1);
}

my @xml_paths = "";
my @stage_list = split(/\s+/,$fev_stage);
my $size = @stage_list;

my $flag = 0;
my $tot = 0;
my $sum = 0;
my $file_flag = 0;
my @fin_stat;
my @fin_viol;
my @gol_list = ();
my @rev_list = ();
my @gol_upf_list = ();
my @rev_upf_list = ();
my @waiver_files = ();
my @viol_files = ();
my $stage_value;


# Define location of run data
if($opt_path eq "") {
    $flow_run_path = $ENV{"ward"} . "/runs/$opt_build_dir/$opt_tech/$opt_run_dir";
} else {
    $flow_run_path = "$opt_path/runs/$opt_build_dir/$opt_tech/$opt_run_dir";
}
#Path existence is not required for fev_checker.pl
#if(!-d $flow_run_path) {
#  print "INTEL_ERROR : '$flow_run_path' is not a valid directory. Cannot continue.\n";
#  exit(1);
#}

foreach (@stage_list) {
    my $stage = $_;
    $stage_value = $stage;
    my $path_n = "$flow_run_path/$stage/IF_${opt_design}_$stage/outputs/$opt_design.$stage.violations.xml";
    my $vio_dir = "$flow_run_path/$stage/IF_${opt_design}_$stage/outputs/violation_rpts";
    chomp($path_n);
    if (!-e $path_n) {
        $file_flag++;
    }
    if ($file_flag == 0) {
        #proceed with the checks
    } else {
        # As per the Closure Resources wiki, "The XML file must always be created." so changing error+exit to a closure check instead.
        # https://wiki.ith.intel.com/display/cheetah/Closure+Resources
        print "INTEL_EROR: Required violation.xml $path_n is not present for $stage, cant proceed with further closure checks.\n";
        my $description = "Required $stage violations.xml exists";
        my $check_id    = "$stage\_violations_xml_exists";
        my $check = Closure::Check->new(DESCRIPTION => $description,
                                        UNIQUE_ID   => $check_id);
        my $filename = basename $path_n;
        $check->addError("Required $filename for stage=$stage does not exist");
        $check->addMissingPath($path_n);
        $check->addIndicator("ERROR");
        $dataObj->addCheck($check);
        next;
    }

    ##First Check
    my $description = "$stage InspectFEV Audit run completion and final status";
    my $check_id    = "$stage\_InspectFEV_FINAL_RESULT";
    my $check = Closure::Check->new(DESCRIPTION => $description,
                                    UNIQUE_ID   => $check_id);
    my $dom = XML::LibXML->load_xml(location => $path_n);
    if ($stage =~ /rtl/) {
        my $x_rev = $dom->findnodes('//revnetlistchksum');
        push @rev_list,"$x_rev";
        my $x_upfrev = $dom->findnodes('//revupfchksum');
        push @rev_upf_list,"$x_upfrev";
    } else {
        my $x_gol = $dom->findnodes('//golnetlistchksum');
        push @gol_list,"$x_gol";
        my $x_upfgol = $dom->findnodes('//golupfchksum');
        push @gol_upf_list,"$x_upfgol";
    }
    foreach my $mov ($dom->findnodes('//check')) {
        if  (($mov->findvalue('./uniq_id')) eq "$stage\_Total_rem_viol") {
            #print $mov->findvalue('./pass|fail');
            my $f_stat = "";
            my $val = $mov->findvalue('./pass|fail');
            if ($val =~ /^(PASS|FAIL)/ && $opt_nogreenstone_mode == 1) {
                $check->setPass("InspectFEV run has completed successfully and required violation.xml for $stage is generated.");
                $check->addPath($path_n);
            } elsif ($val =~ /^PASS:\s+This(.*)violations,total_vio:(\d+),user_waived:(\d+)/) {
                my $user_waived_count = $3;
                $f_stat = "PASS";
                $check->addInfo("InspectFEV run has completed successfully and required violation.xml $path_n for $stage is generated.");
                if ($user_waived_count == 0) {
                    $check->setPass("$f_stat: There are 0 remaining violations, Total violations: $2 , Total User_waived: $3 .Final status is PASS.");
                } else {
                    @waiver_files = glob "$flow_run_path/$stage/IF_${opt_design}_$stage/waivers/*.waivers";
                    foreach my $s (@waiver_files) {
                        chomp($s);
                        (my $rulename,my $dir,my $ext) = fileparse($s,'\.waivers');
                        open(SH,"<$s") || die "-F- Could not open $s for reading.\n";
                        while(my $line = <SH>) {
                            chomp($line);
                                #print $line;
                            next if($line =~ /^\#/);
                            next if($line =~ /^\s*$/);
                            $check->addAutowaiver("$rulename : $line");
                        }
                        $check->addPath($s);
                    }
                    close(SH);
                }
            } elsif ($val =~ /^FAIL:\s+This check has failed with (\d+) violations,total_vio:(\d+),user_waived:(\d+)/) {
                $f_stat ="FAIL:";
                $flag++;
                push @fin_viol,$1;
                $check->addInfo("InspectFEV run has completed successfully and required violation.xml $path_n for $stage is generated.");
                $check->addFailure("$f_stat There are $1 total remaining violations , Total violations: $2 , Total User_waived: $3. Final status is FAIL.");
                @waiver_files = glob "$flow_run_path/$stage/IF_${opt_design}_$stage/waivers/*.waivers";
                foreach my $s (@waiver_files) {
                    chomp($s);
                    (my $rulename,my $dir,my $ext) = fileparse($s,'\.waivers');
                    open(SH,"<$s") || die "-F- Could not open $s for reading.\n";
                    while(my $line = <SH>) {
                        chomp($line);
                        #print $line;
                        next if($line =~ /^\#/);
                        next if($line =~ /^\s*$/);
                        $check->addAutowaiver("$rulename : $line");
                    }
                    $check->addPath($s);
                }
                close(SH);
            } else {
                $check->addError("ERROR: InspectFEV run has not completed therefore required violation.xml for $stage is not complete.");
                $check->addMissingPath($path_n);
            }

            my $path_sum = "$flow_run_path/$stage/IF_${opt_design}_$stage/results/Greenstone_summary.rpt";
            $check->addPath($path_sum);
            $dataObj->addCheck($check);
        }
    }
    if ($opt_nogreenstone_mode == 1) {

        # Get all report files
        my @report_files = sort glob("$vio_dir/*{.rpt,.rpt.gz}");

        foreach my $report (@report_files) {
            # Use name of report as rule name, remove .rpt extension
            my $rule = basename $report;
            $rule =~ s/\.rpt(\.gz)?//;

            my $description = "Reports $stage $rule violations";
            my $check_id    = "$stage\_$rule";
            my $check = Closure::Check->new(DESCRIPTION => $description,
                                            UNIQUE_ID   => $check_id);

            # Open report
            open(my $IN, "/usr/bin/zcat -f $report|") || die "-F- Could not open $report for reading.\n";

            my $header = "";
            my $header_template;
            my @columns;
            my $fail_count = 0;
            while(<$IN>) {
                chomp;

                # Skip empty lines
                next if (/^\s*$/);
                # For skipping info table at top of Inspect FEV Reports
                
                #***********************************
                #Rule: CheckforGeneralError
                #Rule_Category: DesignQuality
                #TIMESTAMP: Mon May  2 10:31:54 PDT 2022
                #HOSTNAME: scc445063.zsc11.intel.com
                #USER: dghand
                #***********************************
                next if (/^#\*+/);
                next if (/^#Rule/);
                next if (/^#TIMESTAMP:/);
                next if (/^#HOSTNAME:/);
                next if (/^#USER:/);
                next if (/^#-+/);

                # Parse header of violation table
                if ($header eq "") {
                    $header = $_;

                    # Parse fixed-width files
                    # https://stackoverflow.com/a/4911211
                    my @template = map {'A'.length} # convert each to 'A##'
                    $header =~ /(\S+\s*)/g; # split first line into segments
                    $template[-1] = 'A*'; # set the last segment to be slurpy
                    $header_template = "@template";

                    @columns = unpack $header_template, $header;

                    # Remove leading # from any column names
                    map {s/#//g} @columns;
                    next;
                }
                
                my $cnt = 0;
                # Use header template to unpack violation lines
                my @line = unpack $header_template, $_;
                my $violation_line;
                for (my $i=0 ; $i <= $#line ; $i++) {
                    # Skip "key" field as it provides no value
                    next if ($columns[$i] eq "Key");
                    # Remove any leading or trailing spaces
                    $line[$i] =~ s/^\s+|\s+$//g;
                    # Append to violation line
                    $violation_line .= "$columns[$i]=\"$line[$i]\"  ";
                }
                # Remove any trailing spaces
                $violation_line =~ s/\s+$//;
                # Add failure line
                $check->addFailure("$violation_line");
                $fail_count++;
            }
            close $IN;

            # Report pass if there are no failures
            if ($fail_count == 0) {
                $check->setPass("$rule has no violations");
            }
            # Add indicator
            $check->addIndicator($fail_count);
            # Add violation report path
            $check->addPath($report);
            # Add check
            $dataObj->addCheck($check);
        }
    }
}

# Only do the below checks if the original violations.xml was found
if ($file_flag == 0) {
	##Netlist checksum
	my $cksum_list = 0;
	if ($size > 1) {
	    if ($rev_list[0] ne $gol_list[0]) {
	        $cksum_list++;
	    }
	} else {
	}
	
	##UPF checksum
	my $cksum_upflist = 0;
	if ($size > 1) {
	    if ($rev_upf_list[0] ne $gol_upf_list[0]) {
	        $cksum_upflist++;
	    }
	}
	
	my @sum_array;
	my $iter_sum = 0;
	for my $each (@fin_viol) {
	    $iter_sum += $each;
	    push @sum_array, $iter_sum;
	}
	{
		my $check = Closure::Check->new(DESCRIPTION => "Final netlist checksum summary",
	                                     UNIQUE_ID   => "netlist_cksum");
		if ($cksum_list ==0) {
			$check->setPass("Final netlist checksum status is PASS.");
			if ($size > 1) {
				$check->addInfo("Golden netlist checksum : @gol_list , Revised netlist checksum : @rev_list");
				$check->addInfo("Please look for the checksum values in logfile logs/lec.log");
			}
		} else {
			$check->addFailure("Final netlist checksum status is Fail.");
			if ($size > 1) {
				$check->addInfo("Golden Netlist checksum : @gol_list , Revised netlist checksum : @rev_list");
				$check->addInfo("Please look for the checksum values in logfile logs/lec.log");
			}
		}
		$dataObj->addCheck($check);
	}
	{
		my $check = Closure::Check->new(DESCRIPTION => "Final upf checksum summary",
	                                     UNIQUE_ID   => "upf_cksum");
		if ($cksum_upflist ==0) {
			$check->setPass("Final upf checksum status is PASS.");
			if ($size > 1) {
				$check->addInfo("Golden upf checksum : @gol_upf_list , Revised upf checksum : @rev_upf_list");
				$check->addInfo("Please look for the checksum values in logfile logs/lec.log");
			}
		} else {
			$check->addFailure("Final upf checksum status is Fail.");
			if ($size > 1) {
				$check->addInfo("Golden upf checksum : @gol_upf_list , Revised upf checksum : @rev_upf_list");
				$check->addInfo("Please look for the checksum values in logfile logs/lec.log");
			}
		}
		$dataObj->addCheck($check);
	}
	if ($opt_nogreenstone_mode == 0) {
	my $check = Closure::Check->new(DESCRIPTION => "Final Closure Status",
	                                UNIQUE_ID   => "final_status_for_closure");
	if ($flag == 0 && $cksum_list == 0 && $cksum_upflist == 0) {
		$check->setPass("Final Closure status is PASS as there are no remaining violations and checksum of netlist/upf is equal.");
	} else {
		if ($flag != 0 && $cksum_list == 0 && $cksum_upflist == 0) {
			$check->addFailure("FAIL:There are $sum_array[-1] remaining Audit violations , Final status is Fail.");
		} elsif ($flag != 0 && $cksum_list != 0 && $cksum_upflist == 0) {
			$check->addFailure("FAIL:There are $sum_array[-1] remaining Audit violations  and the checksum of netlist is not equal, Final status is Fail.");
		} elsif ($flag != 0 && $cksum_list == 0 && $cksum_upflist != 0) {
			$check->addFailure("FAIL:There are $sum_array[-1] remaining Audit violations  and the checksum of upf is not equal, Final status is Fail.");
		} elsif ($flag != 0 && $cksum_list != 0 && $cksum_upflist != 0) {
			$check->addFailure("FAIL:There are $sum_array[-1] remaining Audit violations and the checksum of upf,netlist is not equal, Final status is Fail.");
		} elsif ($flag == 0 && $cksum_list == 0 && $cksum_upflist != 0) {
			$check->addFailure("FAIL:There are 0 remaining Audit violations and the checksum of netlist is equal but checksum of upf is not equal, Final status is Fail.");
		} elsif ($flag == 0 && $cksum_list != 0 && $cksum_upflist == 0) {
			$check->addFailure("FAIL:There are 0 remaining Audit violations  and the checksum of upf is equal but the checksum of netlist , Final status is Fail.");
		} elsif ($flag == 0 && $cksum_list != 0 && $cksum_upflist != 0) {
			$check->addFailure("FAIL:There are 0 remaining Audit violations but the checksum of upf,netlist is not equal, Final status is Fail.");
		} else {
		#do nothing
		}
	}
	$dataObj->addCheck($check);
	}
} # End: if ($file_flag == 0)
$dataObj->saveToFile($opt_output_file);
print "INTEL_INFO: Created $opt_output_file\n";

