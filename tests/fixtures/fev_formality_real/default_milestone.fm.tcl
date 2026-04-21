####################################################################################################
####################################################################################################
#
#                                                                     
#
#
####################################################################################################


global env ERRGEN_RULES ERRGEN_CONFIG ERRGEN_SVRTY ERRGEN_HEADER ERRGEN_LP task fev_type enable_approvals milestone stepping project max_viol

set max_viol ""
if { [info exists env(MILESTONE)] } {
    set milestone "$env(MILESTONE)"
} else {
    set milestone "0p3"
}
if { [info exists env(STEPPING)] } {
    set stepping "$env(STEPPING)"
} else {
    set stepping "A0"
}
if { [info exists env(PROJECT)] } {
    set project "$env(PROJECT)"
} else {
    set project "pesg"
}
set enable_approvals 0

##Modifying the rule configs for fev_lite variant
if { $fev_type == "fev_fm_lite" } {
	change_config VerificationFailed 0
	change_config Abort 0
	change_config NonEquivalent 0
	change_config CheckLPViolations 0
	change_config UnmappedPins 0
	change_config MetaflopErrgen 0 
	change_config CheckFevDotTcl 0 
	change_config CheckSigTable 0
	change_config NonMatchingBBoxes 0	
	change_config UserInterfaceMapping 0
	change_config CheckBadRenamingRules 0
	change_config CheckVLOGSixtyFour 0
	change_config CheckSeqConstX 1
	change_config SupplyCheckNonEq 0
	change_config SupplyCheckUnmatched 0
	change_config Unverified 0
}

if { $fev_type == "r2g" } {
	change_config CheckSeqConstX 1 
	if { ! $ivar($task,golden_v2k_config) || ! $ivar($task,revised_v2k_config) } {
		change_config VtoKErrgen 0 
	}
}

##Modifying the rule configs for g2g fev variant
if { $fev_type == "g2g" } {
	change_config CheckFevDotTcl 0
	change_config CheckParameterizedBBoxes 0
	change_config CheckSeqConstX 1
}

##Modifying the rule configs for r2r fev variant
if { $fev_type == "r2r" } {
	change_config CheckFevDotTcl 0
	change_config CheckVLOGSixtyFour 0
	change_config MetaflopErrgen 0
	if { ! $ivar($task,golden_v2k_config) || ! $ivar($task,revised_v2k_config) } {
		change_config VtoKErrgen 0 
	}
}

if { ($milestone == "1p0" || $milestone == "P10") && ($fev_type == "r2g") } {
	change_config CheckSigTable 1 
}
