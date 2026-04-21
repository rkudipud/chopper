####################################################################################################
####################################################################################################
#
#                                                                     
#
#
####################################################################################################


#-- Last code rework - 2024.03


################################################################################
#proc	    : read_libs										
#purpose    : To read Synopsys .db designs or technology libraries for LP and Non-LP runs   
#usage	    : read_libs
################################################################################
proc read_libs {} {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "read_libs procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global env ivar 
    set task $ivar(task)

    if { [info exists ivar($task,enable_read_libs)] && (!$ivar($task,enable_read_libs)) } {
		iproc_msg -info "read_libs is disabled for this run"
        return
    } 

    iproc_msg -info "Reading technology libs"
    if { [info exists ivar($task,scenario_name)] && $ivar($task,scenario_name) != "" } {
        set scenario_used $ivar($task,scenario_name)
    } elseif { [info exists ivar(setup,hip_oc_types_list)] && $ivar(setup,hip_oc_types_list) != "" }  {
        set scenario_used [lindex $ivar(setup,hip_oc_types_list) 0]	
    } else {	
        set scenario_used [lindex $ivar(setup,oc_types_list) 0]
    }
    
    iproc_msg -info "Using $scenario_used for fetching tech  libs"
    set LDBS ""

    set iter_hip_lib_oc "$ivar(setup,oc_types_list) $ivar(setup,hip_oc_types_list)" 
    foreach linkLib $ivar(link_libs) {
        if { [info exists ivar(lib,$linkLib,use_ccs)] && !$ivar(lib,$linkLib,use_ccs) } {
            if { [info exists ivar(lib,$linkLib,db_nldm_filelist,$scenario_used)] && $ivar(lib,$linkLib,db_nldm_filelist,$scenario_used) != "" } {
                set LDBS_tmp "$ivar(lib,$linkLib,db_nldm_filelist,$scenario_used)"
            } else {
                foreach oc $iter_hip_lib_oc {
                    if { [info exists ivar(lib,$linkLib,db_nldm_filelist,$oc)] && $ivar(lib,$linkLib,db_nldm_filelist,$oc) != "" } {
                        set LDBS_tmp "$ivar(lib,$linkLib,db_nldm_filelist,$oc)"
                        break
                    } else {		
                        set LDBS_tmp ""
                    }
                }
            }	
        } else {
            if { [info exists ivar(lib,$linkLib,db_ccs_filelist,$scenario_used)] && $ivar(lib,$linkLib,db_ccs_filelist,$scenario_used) != "" } {
                set LDBS_tmp "$ivar(lib,$linkLib,db_ccs_filelist,$scenario_used)"
            } else {
                foreach oc $iter_hip_lib_oc {
                    if { [info exists ivar(lib,$linkLib,db_ccs_filelist,$oc)] && $ivar(lib,$linkLib,db_ccs_filelist,$oc) != "" } {
                        set LDBS_tmp "$ivar(lib,$linkLib,db_ccs_filelist,$oc)"
                        break
                    } else {
                        set LDBS_tmp ""
                    }
                }
            }
        }	
        
        set tmpLib [lindex $LDBS_tmp 0]
        if { [file exists $tmpLib] } {
            set LDBS "$LDBS $tmpLib"
        } else { 
            iproc_msg -warning "DB not found for link_lib: $linkLib"
        }
        
    }
    if { $LDBS == "" } { 
        iproc_msg -error "Technology library files not defined" 
    } else {
        iproc_msg -info "Use Technology libraries: $LDBS"
        read_db -technology_library $LDBS
    }

	set_direction -shared_lib [get_lib_pins -quiet -of [get_lib_cells -quiet r:/*/*] -filter "direction==inout && (pg_type==primary_power || pg_type==primary_ground)"] in

    iproc_msg -info "Stage_for_runtime_aggregation read_lib"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"
    
}
define_proc_attributes read_libs \
   -info "To read Synopsys .db designs or technology libraries for LP and Non-LP runs"


################################################################################
#proc	    : read_rtl_2stage 											
#purpose    : To infer 2stage RTL list - to read verilog and vhdl files from rtl list   
#usage	    : read_rtl_2stage <RTL LIST PATH> <TOP MODULE> <container> <ctech_type>
################################################################################
proc read_rtl_2stage { rtlfile root_module { container "r" } { ctech_type "ADD" } } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "read_rtl_2stage procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global env ivar
    set task $ivar(task)
    
    if { ![file exists $rtlfile] } {
        iproc_msg -error "$rtlfile does not exist" 
        exit -1    
    } 
   
    if { $container eq "r" } {
        set side "golden"
    } else {
        set side "revised"
    }

    if { [info exists ivar($task,${side}_v2k_config)] && $ivar($task,${side}_v2k_config)} {
        set_app_var hdlin_enable_verilog_configurations true
        set_app_var hdlin_enable_verilog_configurations_array_n_block true
    }  
    
    puts "Reading"
    puts "   container:  $container"
    puts "   ctech_type: $ctech_type"
    puts "   file list:  $rtlfile"
   
   	
    #stop fm from treating cells with `celldefine as lib cells
    set_app_var fm_ignore_tick_cell_define true
    
    if { $ctech_type eq "ADD" } {
        set ADDITIONAL_RTL_DEFINES "DC INTEL_DC "
        #HSD 22013984456
        set_app_var hdlin_ignore_map_to_operator false
    } else {
        set ADDITIONAL_RTL_DEFINES ""
        set_app_var hdlin_ignore_map_to_operator true 
    }
    
    set LIBLIST ""
    set save_search_path [get_app_var search_path]
    set read_opts ""
    source $rtlfile
    
    #iakolmyc: this section needed to resolve Ctech instances when Ctech library is not explicetly mentioned in v2k config. Otherwise FE-LINK-2 error will be issues.
    #iakolmyc: due to current limitation of Formality set_simulation_setup_file command can be called only once and will affect both, $ref and $impl. Adding 'if' statement to avoid second call during rtl2rtl flow
    set f_name ./synopsys_sim.setup
    iproc_msg -info "Creating file $f_name"
    set SIM_FILE [open $f_name w]
    puts $SIM_FILE "WORK > DEFAULT"
    puts $SIM_FILE "DEFAULT : ./work"
    #puts $SIM_FILE "WORK_lib : ./work_lib"
    for { set i 1 } { $i <= $i_numips } { incr i } {
        set ip_name [set IP_MODULE_NAME_$i]
        puts $SIM_FILE "$ip_name : ./$ip_name"
    } 
    close $SIM_FILE
    set_simulation_setup_file $f_name
    
    for { set i 1 } { $i <= $i_numips } { incr i } {
        set ip_name [set IP_MODULE_NAME_$i]
        if { $ip_name == "dware" } {
            iproc_msg -info "Skipping read of DesignWare RTL from dware filelist."
            continue
        }
        iproc_msg -info "Reading unit RTL for ($i) $ip_name"
        if { [info exists G_RTL_SEARCH_PATH_$i] } {
            set_app_var search_path "[set G_RTL_SEARCH_PATH_$i]"
        }
		# Adding defines for units
        set def_list ""
        set remove_def ""
        if { [info exists RTL_DEFINES_$i] && [set RTL_DEFINES_$i] != "" } {
            set RTL_DEFINES [set  RTL_DEFINES_$i]
            iproc_msg -info "Golden: Defines List for unit $ip_name is RTL_DEFINES_$i"
            ##Removing user provided defines
            if { [info exists ivar($task,${side}_user_remove_defines)] && $ivar($task,${side}_user_remove_defines) != "" } {
                foreach remove_def $ivar($task,${side}_user_remove_defines) {
                    iproc_msg -warning "Removing $remove_def from the defines list(user input)"
                    set RTL_DEFINES [lsearch -inline -all -exact -not $RTL_DEFINES $remove_def]
                }
            }

            foreach def $RTL_DEFINES {
                append def_list "$def "
            }
        }
        ##Adding user defines
        set user_define_list ""
        if { [info exists ivar($task,${side}_user_defines)] && $ivar($task,${side}_user_defines) != "" } {
            foreach def $ivar($task,${side}_user_defines) {
                append def_list "$def "
            }
        }
        append def_list $ADDITIONAL_RTL_DEFINES
		iproc_msg -info "$def_list"
        
        #read design VHDL
        if { [info exists IP_VHDL_FORMAT_$i] && [set IP_VHDL_FORMAT_$i] != "" } {
            set hdlin_vhdl_std [set IP_VHDL_FORMAT_$i]
        } else {
            set hdlin_vhdl_std 1993
        }
        if { [info exists READ_DESIGN_OPTIONS_$i] && [set READ_DESIGN_OPTIONS_$i] != "{}" } {
            set read_opts [set READ_DESIGN_OPTIONS_$i]
            regsub -all {\-file} $read_opts "" read_opts
            regsub -all {\-append} $read_opts "" read_opts
        }
        if { [info exists VERILOG_CTECH_FILES_${ctech_type}_$i] && [set VERILOG_CTECH_FILES_${ctech_type}_$i] != "" } {
            if { [lsearch $LIBLIST $ip_name] < 0 } { lappend LIBLIST $ip_name }
            set VERILOG_CTECH_FILES [set VERILOG_CTECH_FILES_${ctech_type}_$i]
			if { [llength $def_list] > 0 } {
				read_sverilog -$container -libname ${ip_name} -define "$def_list" \{$VERILOG_CTECH_FILES\} 
			} else {
				read_sverilog -$container -libname ${ip_name} \{$VERILOG_CTECH_FILES\} 
			}
        }
        
        if { [info exists VERILOG_SOURCE_FILES_$i] && [set VERILOG_SOURCE_FILES_$i] != "" } {
            if { [lsearch $LIBLIST $ip_name] < 0 } { lappend LIBLIST $ip_name }
            set VERILOG_SOURCE_FILES [set VERILOG_SOURCE_FILES_$i]
            if { [info exists read_opts] && $read_opts != "" } {
                set vcs_options "+libext+.v+.vs+.sv+.vh+.svh+.va+.vb+.vb.gz+. -f $read_opts"
				if { [llength $def_list] > 0 } {
                	read_sverilog -$container -libname ${ip_name} -define "$def_list" -vcs $vcs_options \{$VERILOG_SOURCE_FILES\}   
				} else {
                	read_sverilog -$container -libname ${ip_name} -vcs $vcs_options \{$VERILOG_SOURCE_FILES\}   
				}
            }  else {
				if { [llength $def_list] > 0 } {
                	read_sverilog -$container -libname ${ip_name} -define "$def_list" \{$VERILOG_SOURCE_FILES\} 
				} else {
                	read_sverilog -$container -libname ${ip_name} \{$VERILOG_SOURCE_FILES\} 
				}
            }
        }    
        if { [info exists VHDL_CTECH_FILES_${ctech_type}_$i] && [set VHDL_CTECH_FILES_${ctech_type}_$i] != "" } {
            if { [lsearch $LIBLIST $ip_name] < 0 } { lappend LIBLIST $ip_name }
            set VHDL_CTECH_FILES [set VHDL_CTECH_FILES_${ctech_type}_$i]
            read_vhdl -$container -libname ${ip_name} \{$VHDL_CTECH_FILES\} 
        }
        if { [info exists VHDL_SOURCE_FILES_$i] && [set VHDL_SOURCE_FILES_$i] != "" } {
            if { [lsearch $LIBLIST $ip_name] < 0 } { lappend LIBLIST $ip_name }
            set VHDL_SOURCE_FILES [set VHDL_SOURCE_FILES_$i]
            read_vhdl -$container -libname ${ip_name} \{$VHDL_SOURCE_FILES\}
        }
    }

    set_app_var search_path ""    
    set v_params ""
    if { [info exists ivar(elab_params)] && $ivar(elab_params) ne "" }  {
        regsub -all {=>} $ivar(elab_params) {<=} v_params
    }
    if { [info exists ivar(design_name_rtl)] && $ivar(design_name_rtl) ne "" }  {
        set root_module $ivar(design_name_rtl)
    }
    if  { $v_params ne "" } {

        if { [info exists ivar($task,${side}_v2k_config)] && $ivar($task,${side}_v2k_config) } {
            if { ![set_top -config $container:/${ip_name}/gold_config -parameter $v_params -liblist $LIBLIST -liblist_nocelldiff] } {
				iproc_msg -error "set_top failed"
				exit -1
			}
        } else {
            if { ![set_top $container:/*/$root_module -parameter $v_params] } {
				iproc_msg -error "set_top failed"
				exit -1
			}
        }
    } else {
        if { [info exists ivar($task,${side}_v2k_config)] && $ivar($task,${side}_v2k_config) } {
            if { ![set_top -config $container:/${ip_name}/gold_config -liblist $LIBLIST -liblist_nocelldiff] } {
				iproc_msg -error "set_top failed"
				exit -1
			}
        } else {
            if { ![set_top $container:/*/$root_module] } {
				iproc_msg -error "set_top failed"
				exit -1
			}
        }
    }
    set_app_var search_path $save_search_path
    remove_simulation_setup_file 
    file delete $f_name
    iproc_msg -info "Stage_for_runtime_aggregation read_rtl_2stage"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"
}
define_proc_attributes read_rtl_2stage \
   -info "To infer 2stage RTL list - to read verilog and vhdl files from rtl list"


################################################################################
#proc	    : read_rtl_dotf 											
#purpose    : To infer dot f RTL list - to read verilog and vhdl files from rtl list   
#usage	    : read_rtl_dotf <RTL LIST PATH> <TOP MODULE> <container> <ctech_type>
################################################################################
proc read_rtl_dotf { dotfile root_module { container "r" } { ctech_type "ADD" } } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "read_rtl_dotf procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################

    global env ivar MODEL_ROOT FILELIST_DIR
    set task $ivar(task)

    if { ![file exists $dotfile] } {
        iproc_msg -error "$dotfile dir does not exist"
        exit -1
    } else {
        iproc_msg -info "Reading"
        iproc_msg -info "   container:  $container"
        iproc_msg -info "   ctech_type: $ctech_type"
        iproc_msg -info "   file list:  $dotfile"
   
        if { $container eq "r" } {
            set side "golden"
        } else {
            set side "revised"
        }
        
        #stop fm from treating cells with `celldefine as lib cells
        set_app_var fm_ignore_tick_cell_define true
        
        if { $ctech_type eq "ADD" } {
            set dotf_type "SYN"
            set ADDITIONAL_RTL_DEFINES "DC INTEL_DC "
            #HSD 22013984456
            set_app_var hdlin_ignore_map_to_operator false
        } else {
            set dotf_type "RTL"
            set ADDITIONAL_RTL_DEFINES ""
            set_app_var hdlin_ignore_map_to_operator true 
        }

        ##Adding user defines
        if { [info exists ivar($task,${side}_user_defines) ] && $ivar($task,${side}_user_defines) != "" } {
            foreach def $ivar($task,${side}_user_defines) {
                append ADDITIONAL_RTL_DEFINES "$def "
            }
        }

        if { [info exists ivar($task,dotf_global_defines)] && $ivar($task,dotf_global_defines) != "" } {
            foreach def $ivar($task,dotf_global_defines) {
                append ADDITIONAL_RTL_DEFINES "$def "
            }
        }

        # sourcing the rtl_list_f.tcl file
        if { [catch {source $dotfile} errMsg] } {
            iproc_msg -error "Failed to source $dotfile: $errMsg"
            exit -1
        }

        ## Early check for V2k config presence
        if { [info exists ivar($task,${side}_v2k_config)] && $ivar($task,${side}_v2k_config)} {
            if { [info exists CONFIG_NAME] && $CONFIG_NAME ne "" } {
                iproc_msg -info "ivar($task,${side}_v2k_config) is set and root config_name is present in RTL list"
                set_app_var hdlin_enable_verilog_configurations true
                set_app_var hdlin_enable_verilog_configurations_array_n_block true
            } else {
                iproc_msg -error "ivar($task,${side}_v2k_config) is set and root config_name is not present in RTL list"
                exit -1
            }
        }

        if { [info exists FILELIST_DIR] && $FILELIST_DIR ne "" } {
            set ::FILELIST_DIR $FILELIST_DIR
        }

        if { ![info exists DESIGN_LIB_ORDER] || ![llength $DESIGN_LIB_ORDER] } {
            iproc_msg -error "DESIGN_LIB_ORDER not defined correctly in $dotfile"
            exit -1
        } else {
            foreach lib_name $DESIGN_LIB_ORDER {
                set read_opts ""
                if { [info exists LIB_DEPEND("$lib_name")] && [llength $LIB_DEPEND("$lib_name")] } {
                    append read_opts "-uses $LIB_DEPEND(\"$lib_name\")"
                }
                set f_files ""
                if { [info exists LIB_DOTF_${dotf_type}("$lib_name,vhdl")] && [llength [set LIB_DOTF_${dotf_type}("$lib_name,vhdl")]] } {
                    foreach f_file [set LIB_DOTF_${dotf_type}("$lib_name,vhdl")] {
                        append f_files " -f $f_file"
                    }
                    if { [llength $ADDITIONAL_RTL_DEFINES] > 0 } {
                        set command "read_vhdl -$container -libname $lib_name -define \"$ADDITIONAL_RTL_DEFINES\" -vcs \"$f_files\" $read_opts"
                    } else {
                        set command "read_vhdl -$container -libname $lib_name -vcs \"$f_files\" $read_opts"
                    }
                    iproc_msg -info "Executing $command"
                    if { [catch {eval $command} errMsg] } {
                        iproc_msg -error "Failed to read VHDL for library $lib_name: $errMsg"
                        exit -1
                    }
                } elseif { [info exists LIB_DOTF_${dotf_type}("$lib_name,sv")] && [llength [set LIB_DOTF_${dotf_type}("$lib_name,sv")]] } {
                    foreach f_file [set LIB_DOTF_${dotf_type}("$lib_name,sv")] {
                        append f_files " -f $f_file"
                    }
                    if { [info exists CTECH_DOTF_${dotf_type}] && [set CTECH_DOTF_${dotf_type}] != "" } {
                        append f_files " -f [set CTECH_DOTF_${dotf_type}]"
                    }
                    if { [llength $ADDITIONAL_RTL_DEFINES] > 0 } {
                        set command "read_sverilog -$container -libname $lib_name -define \"$ADDITIONAL_RTL_DEFINES\" -vcs \"$f_files\"  $read_opts"
                    } else {
                        set command "read_sverilog -$container -libname $lib_name -vcs \"$f_files\"  $read_opts"
                    }
                    iproc_msg -info "Executing $command"
                    if { [catch {eval $command} errMsg] } {
                        iproc_msg -error "Failed to read SystemVerilog for library $lib_name: $errMsg"
                        exit -1
                    }
                } else {
                    iproc_msg -error "LIB_DOTF not defined correctly for $lib_name in $dotfile"
                    exit -1
                }
            }
        }

        # if v2k is enabled
        if { [info exists ivar($task,${side}_v2k_config)] && $ivar($task,${side}_v2k_config)} {
            if { [info exists LIB_DOTF_${dotf_type}("h2b_v2k_lib,sv")] && [llength [set LIB_DOTF_${dotf_type}("h2b_v2k_lib,sv")]] } {
                if { [catch {set_top -config $container:/h2b_v2k_lib/$CONFIG_NAME} errMsg] } {
                    iproc_msg -error "set_top failed for V2K config: $errMsg"
                    exit -1
                }
            } else {
                iproc_msg -error "No details found for h2b_v2k_lib"
                exit -1
            }
        } else {
            # if v2k is disabled
            if { [info exists TOP_LIB_NAME] && $TOP_LIB_NAME ne "" } {
                if { [catch {set_top $container:/$TOP_LIB_NAME/$root_module} errMsg] } {
                    iproc_msg -error "set_top failed: $errMsg"
                    exit -1
                }
            } else {
                iproc_msg -error "TOP_LIB_NAME is not defined"
                exit -1
            }
        }
    }
    
    # cleaning multi scoped variables to avoid accidental usage in later stages
    unset -nocomplain ::FILELIST_DIR
    unset -nocomplain ::MODEL_ROOT

    iproc_msg -info "Stage_for_runtime_aggregation read_rtl_dotf" 
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"
   
}
define_proc_attributes read_rtl_dotf \
   -info "To infer dotf rtl list - to read verilog and vhdl files from rtl_list_f.tcl"


################################################################################
#proc	    : read_rtl_hier_f 											
#purpose    : To infer hier f RTL list - to read verilog and vhdl files from rtl list   
#usage	    : read_rtl_hier f <RTL LIST PATH> <TOP MODULE> <container> <ctech_type>
################################################################################
proc read_rtl_hier_f { rtlfile root_module { container "r" } { ctech_type_local "ADD" } } { 
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "read_rtl_hier_f procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global env CTECH_FLAVOR CTECH_TYPE CTECH_EXP_ROOT CTECH_PROCESS UNITS_LIST
    
    if { [info exists ivar(import_design,ctech_root)] } {
        set CTECH_ROOT $ivar(import_design,ctech_root)
    } else {
        set CTECH_ROOT ""
    } 
    
    if { [info exists ivar(import_design,ctech_exp_root)] } {
        set CTECH_EXP_ROOT $ivar(import_design,ctech_exp_root)
    } else {
        set CTECH_EXP_ROOT ""
    }
    
    if { [info exists ivar(import_design,ctech_process)] } {
        set CTECH_PROCESS $ivar(import_design,ctech_process)
    } else { 
        set CTECH_PROCESS ""
    }
    
    if { [info exists ivar(import_design,ctech_variant)] } {
        set CTECH_FLAVOR $ivar(import_design,ctech_variant)
    } else {
        set CTECH_FLAVOR "" 
    }
    
    if { [info exists ivar(import_design,ctech_type)] } {
        set CTECH_TYPE $ivar(import_design,ctech_type)
    } else {
        set CTECH_TYPE "" 
    }
    
    if { [info exists ivar(import_design,ctech_exp_variant)] } {
        set CTECH_EXP_FLAVOR $ivar(import_design,ctech_exp_variant)
    } else {
        set CTECH_EXP_FLAVOR "" 
    }
    
    set CTECH_USER ""
    if { [info exists ivar(import_design,ctech_user)] } {
        if { [file exists $ivar(import_design,ctech_user)] } {
            set CTECH_USER "-y $ivar(import_design,ctech_user)"
        } else {
            iproc_msg -warning "CTECH_USER private directory doen't exist"
        }
    }
    
    puts "CTECH_ROOT = $CTECH_ROOT"
    if { $CTECH_EXP_ROOT ne "" } {
        puts "CTECH_EXP_ROOT = $CTECH_EXP_ROOT"
    }
    
    puts "CTECH_PROCESS = $CTECH_PROCESS"
    puts "CTECH_TYPE    = $CTECH_TYPE"
    puts "CTECH_FLAVOR = $CTECH_FLAVOR"
    puts "CTECH_EXP_FLAVOR = $CTECH_EXP_FLAVOR"
    set CTECH_VARIANT $CTECH_FLAVOR
    set CTECH_EXP_VARIANT $CTECH_EXP_FLAVOR
    
    set UNITS_LIST ""
    
    if { [file exists $rtlfile] } {
        source $rtlfile
    } else {
        iproc_msg -error "$rtlfile does not exist"
        exit -1
    }
    
    set rtl_defines $ivar(import_design,additional_defines)
    
    if { [info exists TOP_LEVEL_VCS] } {
        iproc_msg -info ".f file analyze methodology invoked " 
		if { [llength $rtl_defines] > 0 } {
			set base_cmd "read_sverilog -$container -define \"$rtl_defines\"  -vcs { -f $::TOP_LEVEL_VCS } "
		} else {
			set base_cmd "read_sverilog -$container -vcs { -f $::TOP_LEVEL_VCS } "
		}
        iproc_msg -info "Analyze command is: $base_cmd "
        eval $base_cmd
    } elseif { [info exists BLOCK_NAME ] &&  [info exists  BLOCK_DOT_F ] &&  [info exists  SUB_BLOCK_DOT_F_LIST ] } {
        iproc_msg -info "Hierarhical .f file analyze methodology invoked "
        # read units 
        set unit_name "test"
        if { [info exists  VHDL_LIB_DOT_F_LIST] } {
            iproc_msg -info "Running in VHDL mode"
            set vhdl_mode 1
            if { [info exists  VERILOG_LIB_DOT_F_LIST] } {
                set SUB_BLOCK_DOT_F_LIST [join [concat $SUB_BLOCK_DOT_F_LIST $VERILOG_LIB_DOT_F_LIST]]
            }
        } else {
            set vhdl_mode 0
        }
        
        # Read Verilog units 
        foreach item $SUB_BLOCK_DOT_F_LIST {                               
            iproc_msg -info "Next - $item"    
            if { [regexp {\.f$} $item] } {
                iproc_msg -info "Analyze .f file - $item "
                set unit_file $item 
				if { [llength $rtl_defines] > 0 } {
					set cmd "read_sverilog -$container -define \"$rtl_defines\" -libname $unit_name -vcs \"  +incdir+$CTECH_ROOT/source/$CTECH_PROCESS/$CTECH_TYPE/$CTECH_VARIANT/ -y $CTECH_ROOT/source/$CTECH_PROCESS/$CTECH_TYPE/$CTECH_VARIANT/  -y $CTECH_EXP_ROOT/source/$CTECH_PROCESS/$CTECH_TYPE/$CTECH_EXP_VARIANT/ $CTECH_USER +libext+.vs +libext+.v +libext+.sv  -f $unit_file\""
				} else {
					set cmd "read_sverilog -$container -libname $unit_name -vcs \"  +incdir+$CTECH_ROOT/source/$CTECH_PROCESS/$CTECH_TYPE/$CTECH_VARIANT/ -y $CTECH_ROOT/source/$CTECH_PROCESS/$CTECH_TYPE/$CTECH_VARIANT/  -y $CTECH_EXP_ROOT/source/$CTECH_PROCESS/$CTECH_TYPE/$CTECH_EXP_VARIANT/ $CTECH_USER +libext+.vs +libext+.v +libext+.sv  -f $unit_file\""
				}
                iproc_msg -info "Executing command: $cmd"
                eval $cmd
                
                if { $vhdl_mode ==0 } {
                    set cmd "##set_top r:/*/$unit_name "
                    iproc_msg -info "Executing command: $cmd"
                    eval $cmd
                }
            } else {
                iproc_msg -info "Next unit name is: $item "
                set unit_name  $item
                lappend  UNITS_LIST $unit_name
            }	
        }
        # Read VHDL units
        if { $vhdl_mode } {
            foreach item $VHDL_LIB_DOT_F_LIST {
                iproc_msg -info "Next - VHDL $item"    
                if { [regexp {\.f$} $item] } {
                    iproc_msg -info "Analyze .f file - $item "
                    set unit_file $item 
                    set fp [open $unit_file  r]
                    while { [gets $fp data] >= 0 } {
                        if { [regexp {//} $data ] } { continue }  
                        if { [regexp {\.vhd} [ file tail $data]] } {
                            set vhdl_analyze_cmd "read_vhdl -$container  -libname $unit_name $data "
                            iproc_msg -info "Executing command: $vhdl_analyze_cmd"
                            eval $vhdl_analyze_cmd
                        }
                    }
                    close $fp
                } else {
                    iproc_msg -info "Next VHDL unit name is: $item "
                    set unit_name  $item
                    #lappend  UNITS_LIST $unit_name
                }	    
            }
        }
        
        #read top level 
		if { [llength $rtl_defines] > 0 } {
			set base_cmd "read_sverilog -$container -define \"$rtl_defines\" -vcs { -f  $BLOCK_DOT_F }" 
		} else {
			set base_cmd "read_sverilog -$container -vcs { -f  $BLOCK_DOT_F }" 
		}
        iproc_msg -info "Analyze command is: $base_cmd "
        eval $base_cmd
    }
    
    if { ![set_top $container:/*/$root_module] } {
		iproc_msg -error "set_top failed"
		exit -1		
	}
    iproc_msg -info "Stage_for_runtime_aggregation read_rtl_hier_f"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"
}
define_proc_attributes read_rtl_hier_f \
    -info "To infer hier f RTL list - to read verilog and vhdl files from rtl list"   


################################################################################
#proc	    : read_gate 											
#purpose    : To read netlist on reference or implemented side
#usage	    : read_gate <NETLIST PATH> <DESIGN NAME> <REF|IMPL>
################################################################################
proc read_gate { gate_list design { side "REF" } } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "read_gate procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global env ivar
    set task $ivar(task)
    
    if { [file exists $gate_list] } {
        set path $gate_list
    } elseif { [file exists ${gate_list}.gz] } {
        set path ${gate_list}.gz
    } else {
        iproc_msg -error "$gate_list NOT found"
        exit -1
    }
    iproc_msg -info "Reading $side side"
    if { $side eq "REF" } {
        set container "r"
        set ivar_side "golden"
    } else {
        set container "i"
        set ivar_side "revised"
    }
    
    read_verilog -libname WORK -$container -netlist $path
    
    if { ![info exists ivar($design,child_modules)] || $ivar($design,child_modules) == "" } {
        iproc_msg -info "No child modules found for $design"
    } else {
        set child_netpath ""
        foreach child $ivar($design,child_modules) {
            if { [info exists ivar($task,$child,${ivar_side}_netlist_extn)] } {
                set netlist_extn $ivar($task,$child,${ivar_side}_netlist_extn)	
            } elseif { [info exists ivar($task,child,${ivar_side}_netlist_extn)] } {
                set netlist_extn $ivar($task,child,${ivar_side}_netlist_extn)	
            } else {
                iproc_msg -warning "No netlist extension is provided, so assuming netlist_extn as pt.v"
                set netlist_extn ".pt.v" 
            }
            
            if { [info exists ivar($task,all,${ivar_side}_path)] && $ivar($task,all,${ivar_side}_path) != "" } {
                set child_net "$ivar($task,all,${ivar_side}_path)/${child}$netlist_extn"
                if { [file exists $child_net] } {
                    set path $child_net
                } elseif { [file exists ${child_net}.gz] } {
                    set path ${child_net}.gz
                } else {
                    ## FCFEV read FCL netlist which always have extra /child/ directory. 
                    # need this as secondary option otherwise have to set ivar for every partition
                    #set child_net "$ivar($task,all,${ivar_side}_path)/$child/icc2/${child}$netlist_extn"
                    set child_net "$ivar($task,all,${ivar_side}_path)/collateral/td/${child}/${child}$netlist_extn"
                    if { [file exists $child_net] } {
                        set path $child_net
                    } elseif { [file exists ${child_net}.gz] } {
                        set path ${child_net}.gz
                    } else {
                        iproc_msg -error "$child_net NOT found"
                        exit -1
                    }
                }
                lappend child_netpath $path
            } elseif { [info exists ivar($task,$child,${ivar_side}_path)] && $ivar($task,$child,${ivar_side}_path) != "" } {
                set child_net "$ivar($task,$child,${ivar_side}_path)/${child}$netlist_extn"
                if { [file exists $child_net] } {
                    set path $child_net
                } elseif { [file exists ${child_net}.gz] } {
                    set path ${child_net}.gz
                } else {
                    iproc_msg -error "$child_net NOT found"
                    exit -1
                }
                lappend child_netpath $path
            }  else {
                iproc_msg -error "$ivar_side design not found for $child, existing"
                exit -1
            }
        }
        
        iproc_msg -info "Reading child netlists"
        read_verilog -libname WORK -$container -netlist $child_netpath
        
    }
    
    if { ![set_top $container:/WORK/$design] } {
		iproc_msg -error "set_top failed"
		exit -1		
	}
    iproc_msg -info "Stage_for_runtime_aggregation read_gate"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"
    
}
define_proc_attributes read_gate \
    -info "To read netlist on reference or implemented side"


################################################################################
#proc	    : read_rtl_1stage
#purpose    : To infer 1 stage RTL list and read RTL
#usage	    : read_rtl_1stage <RTL LIST PATH> <TOP MODULE> <REF|IMPL>
################################################################################
proc read_rtl_1stage { rtl_list design { side "REF" } } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "read_rtl_1stage procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    # test this
    global ivar env
    iproc_msg -info "Reading $side side's file list: $rtl_list"
    if { $side eq "REF" } {
        set container "r"
    } else {
        set container "i"
    }
    source $rtl_list
    iproc_msg -info "search_path: $search_path"
    if { [info exists VERILOG_CTECH_FILES_ADD] && [set VERILOG_CTECH_FILES_ADD] != "" } {
		if { [llength $RTL_DEFINES] > 0 } {
        	read_sverilog -libname WORK -$container -define "$RTL_DEFINES"  \"[concat $VERILOG_SOURCE_FILES [set VERILOG_CTECH_FILES_ADD]]\"
		} else {
        	read_sverilog -libname WORK -$container \"[concat $VERILOG_SOURCE_FILES [set VERILOG_CTECH_FILES_ADD]]\"
		}        
    }
    if { ![set_top $container:/WORK/$design] } {
		iproc_msg -error "set_top failed"
		exit -1
	}
    iproc_msg -info "Stage_for_runtime_aggregation read_rtl_1stage"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"
    
}
define_proc_attributes read_rtl_1stage \
    -info "To infer 1 stage RTL list and read RTL"


################################################################################
#proc	    : report_match_results											
#purpose    : Reports to be dumped out after match happens
#usage	    : report_match_results <DESIGN NAME>
################################################################################
proc report_match_results { design } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "report_match_results procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global ivar env
    
    report_user_matches       > reports/$design.user_matched_points.rpt
    report_matched_points     > reports/$design.matched_points.rpt
	report_matched_points -method function     > reports/$design.matched_points.functional.rpt
	report_matched_points -method topology     >> reports/$design.matched_points.functional.rpt
	report_matched_points -point_type bbox	> reports/$design.matched_points_bboxes.rpt
    report_unmatched_points   > reports/$design.unmatched_points.rpt
    report_unread_endpoints -all > reports/$design.unread_endpoints.rpt
    report_unmatched_points -status undriven -point_type cut -reference > reports/$design.RTL_undrivens.rpt
	report_not_compared_points > reports/$design.not_compared_points.rpt
	report_unmatched_points -status removed > reports/$design.unmatched_points_removed.rpt
	report_unmatched_points -point_type bbox > reports/$design.unmatched_points_bbox.rpt

}
define_proc_attributes report_match_results \
    -info "Reports to be dumped out after match happens"


################################################################################
#proc	    : report_verify_results
#purpose    : Reports to be dumped out after verify 
#usage	    : report_verify_results <DESIGN NAME>
################################################################################
proc report_verify_results { task design fev_type } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "report_verify_results procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global ivar env ref impl verification_status
    
    report_failing_points > reports/$design.failing_points.rpt
    report_passing_points > reports/$design.passing_points.rpt
    report_aborted_points > reports/$design.aborted_points.rpt
    report_unverified_points  > reports/$design.unverified_points.rpt
    report_dont_verify_points > reports/$design.dont_verify_points.rpt
    report_compare_rules $ref   > reports/$design.compare_rules_ref.rpt
    report_compare_rules $impl   > reports/$design.compare_rules_impl.rpt
    report_svf_operation -status accepted   > reports/$design.svf_operations.rpt
    report_svf_operation -status rejected   >> reports/$design.svf_operations.rpt
    report_svf_operation -status unprocessed   >> reports/$design.svf_operations.rpt
    report_svf_operation -status pending   >> reports/$design.svf_operations.rpt
    report_black_boxes        > reports/$design.black_boxes.rpt
    report_black_boxes -summary  -nosplit     > reports/$design.black_boxes_summary.rpt
    report_unmatched_points -reclassify_based_on_verification_result -reference > reports/$design.unmatched_reclassified.rpt
    write_register_mapping -rtlname -bbpin -port -replace reports/$design.register_mapping.rpt
	report_constants	> reports/$design.const.rpt
	report_unmatched_points -point_type port -except_status passing_feedthrough_point -except_status not_targeted > reports/$design.unverified_feedthrough.rpt
    report_unmatched_points -list -reference -status unread > reports/$design.unmatched_unread_ref.rpt
	report_unmatched_points -list -implementation -status unread > reports/$design.unmatched_unread_impl.rpt
	report_constantx_registers -reason_type > reports/$design.seq_constx_all.rpt
	report_app_var > reports/$design.app.options.rpt
    report_status > reports/$design.status.rpt
    report_multidriven_nets > reports/$design.multidriven.rpt


    #modified in 2024.06.SP1 to exclude certain types of names form report
    if { $fev_type eq "g2g" || $fev_type eq "r2r" } {
        if { $verification_status == "SUCCEEDED" } {
            report_constantx_registers -reason_type -except_status { unread unmatched } -implementation -reference -except_substring { test_pipe_se si_tmp temp_cto_reg pwc_clk_gate dft_anchor_ldop LOCKUP wrp0 } > reports/$design.seq_constx.rpt
        } else {
            report_constantx_registers -reason_type -except_status unread -implementation -reference -except_substring { test_pipe_se si_tmp temp_cto_reg pwc_clk_gate dft_anchor_ldop LOCKUP wrp0 } > reports/$design.seq_constx.rpt
        }
    } elseif { $fev_type eq "r2g" } {
        if { $verification_status == "SUCCEEDED" } {
            report_constantx_registers -reason_type -except_status { unread unmatched } -implementation -except_substring { test_pipe_se si_tmp temp_cto_reg pwc_clk_gate dft_anchor_ldop LOCKUP wrp0 } > reports/$design.seq_constx.rpt
        } else {
            report_constantx_registers -reason_type -except_status unread -implementation -except_substring { test_pipe_se si_tmp temp_cto_reg pwc_clk_gate dft_anchor_ldop LOCKUP wrp0 } > reports/$design.seq_constx.rpt
        }
    } 

    #Adding for generating the report for bbox parametrization
    if { ($fev_type ne "g2g") && ($fev_type ne "eco") } {
        report_bboxes_parametrization $fev_type $design
    }    

    annotate_trace -stop
    iproc_msg -info "Generating clk_gate_lat report"
    # it uses special "foreach_in_collection" command to iterate collection.
    set fileId [open "reports/$design.clk_gate_lat.rpt" "w"]
    # Iterate over the collection and write each item to the file
    foreach_in_collection item [all_clock_gating_latches] { 
        puts $fileId [get_attribute $item full_name]
    }
    close $fileId
    annotate_trace -start


    create_inspectfev_config $task $design $fev_type
    iproc_msg -info "Stage_for_runtime_aggregation report_results"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"
}
define_proc_attributes report_verify_results \
    -info "Reports to be dumped out after verify"


################################################################################
#proc	    : additional_matching
#purpose    : To add commands (if any) after match
#usage	    : additional_matching <DESIGN NAME> <TASK>
################################################################################
proc additional_matching { design } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "additional_matching procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global ivar env
    
    #just a place holder for users to add any manual matching
    iproc_msg -info "Stage_for_runtime_aggregation additional_matching"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"
    
}
define_proc_attributes additional_matching \
    -info "To add commands (if any) after match"


##################################################################
#proc	: add_fm_scan_constraints 											
#purpose: Adding constraints for Disabling scan
#usage	: add_fm_scan_constraints {variant design}
###################################################################
proc add_fm_scan_constraints { variant design } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "add_fm_scan_constraints procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global env ivar
    set task $ivar(task)
    
    if { [info exists ivar($task,scan_constraints)] && (!$ivar($task,scan_constraints)) } {
        iproc_msg -info "add_fm_scan_constraints is disabled for this run"
        return
    }
	annotate_trace -stop
    
    iproc_msg -info "Applying Scan constraints for $task"
    #Just a place holder
    iproc_msg -info "Stage_for_runtime_aggregation add_fm_scan_constraints"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"
    
    annotate_trace -start  
}
define_proc_attributes add_fm_scan_constraints \
    -info "Adding constraints for Disabling scan"


##################################################################
#proc	: add_fm_lcp_constraints 											
#purpose: Adding constraints for LCP 
#usage	: add_fm_lcp_constraints {design}
###################################################################
proc add_fm_lcp_constraints { design }  {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "add_fm_lcp_constraints procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global env ivar
    set task $ivar(task)
    
    if { [info exists ivar($task,lcp_constraints)] && (!$ivar($task,lcp_constraints)) } {
        iproc_msg -info "add_fm_lcp_constraints is disabled for this run"
        return
    }
	annotate_trace -stop
    
    iproc_msg -info "Applying LCP constraints for $task"
    #Just a place holder
    iproc_msg -info "Stage_for_runtime_aggregation add_fm_lcp_constraints"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"
    
    annotate_trace -start  
}
define_proc_attributes add_fm_lcp_constraints \
    -info "Adding constraints for LCP"


##################################################################
#proc	: add_fm_td_constraints 											
#purpose: Adding Top Down pushdown constraints
#usage	: add_fm_td_constraints {side variant design}  
###################################################################
proc add_fm_td_constraints { side variant design } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "add_fm_td_constraints procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global ivar env ref impl
    set task $ivar(task)
    
    if { [info exists ivar($task,td_constraints)] && (!$ivar($task,td_constraints)) } {
        iproc_msg -info "add_fm_td_constraints is disabled for this run"
        return
    }
    
    iproc_msg -info "Applying TD constraints for $task"

    current_container i
    
    if { $side eq "REF" } {
        set ivar_side "golden"
    } else {
        set ivar_side "revised"
    }
    
    #set to default value
    set path $ivar($task,fev_dot_tcl_path)
    
    if { [info exists ivar($task,$design,fev_dot_tcl_path)] && $ivar($task,$design,fev_dot_tcl_path) != "" } {
        set path $ivar($task,$design,fev_dot_tcl_path)
    }
    
    if { [file exists "$path/${design}_fev_fm.tcl"] } {
        set bfile "$path/${design}_fev_fm.tcl"
    } elseif { [file exists "$path/$design/${design}_fev_fm.tcl"] } {
        set bfile "$path/$design/${design}_fev_fm.tcl"
    } else {
		regsub $env(ward) "$path/${design}_fev.tcl" {$ward} bfile_tmp
        iproc_msg -error "$bfile_tmp feedthrough file does not exist for $design"
        set bfile ""
    }		
    
    if { [file exists $bfile] } {
        source -echo -verbose $bfile
    }
    
    if { [info exists ivar($task,$design,black_box)] && $ivar($task,$design,black_box) != "" } {
        foreach module $ivar($task,$design,black_box) {
            if { [info exists ivar($task,$design,child_fev_dot_tcl_path)] && $ivar($task,$design,child_fev_dot_tcl_path) != "" } {
                set bfile "$ivar($task,$design,child_fev_dot_tcl_path)/$module/icc2/${module}_fev_fm.tcl"
            } elseif { [info exists ivar($task,$module,${ivar_side}_fev_dot_tcl_path)] && $ivar($task,$module,${ivar_side}_fev_dot_tcl_path) != "" } {
                set bfile "$ivar($task,$module,${ivar_side}_fev_dot_tcl_path)/${module}_fev_fm.tcl"
            } else {
                set bfile "$path/../../collateral/td/$module/${module}_fev_fm.tcl"
            }
            
            if { [file exists $bfile] } {
                iproc_msg -info "Parsing feedthru collateral for bbox $module from $bfile"
                source -echo -verbose $bfile
            } else {
				regsub $env(ward) $bfile {$ward} bfile_tmp
				iproc_msg -error "$bfile_tmp feedthrough file does not exist for $module"	
			}			
        }	
    }
    
    report_feedthrough_points > reports/$design.feedthrough_points.rpt
	iproc_msg -info "Done running: add_fm_td_constraints"
    iproc_msg -info "Stage_for_runtime_aggregation add_fm_td_constraints"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"
}
define_proc_attributes add_fm_td_constraints \
    -info "Adding Top Down pushdown constraints"


##################################################################
#proc	: add_ctech_constraints  											
#purpose: provide generic ctech mapping for rtlvrtl runs 
#usage	: add_ctech_constraints {variant}  
###################################################################
proc add_ctech_constraints { design } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "add_ctech_constraints procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global ivar env impl
    iproc_msg -info "Stage_for_runtime_aggregation add_ctech_constraints"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"
}
define_proc_attributes add_ctech_constraints \
    -info "provide generic ctech mapping for rtlvrtl runs"


##################################################################
#proc	: create_inspectfev_config 											
#purpose: proc that creates necessary config information for inspectFV 
#usage	: create_inspectfev_config {task design fev_type}  
###################################################################
proc create_inspectfev_config { task design fev_type } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "create_inspectfev_config procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global ivar env
    
    set IF_csh "./reports/IF_config_${design}_${task}.csh"
    set bfh [open $IF_csh w]
    puts $bfh "setenv design_name \"$design\""
    puts $bfh "setenv task \"$task\""
    puts $bfh "setenv fev_var \"$fev_type\""
    if { [info exists ivar(bscript_dir)] } {
        puts $bfh "setenv bscripts \"$ivar(bscript_dir)\""
    }	
    if { [info exists ivar(params,milestone)] } {
        puts $bfh "setenv MILESTONE \"$ivar(params,milestone)\""
    }	
    if { [info exists ivar($task,lp)] && $ivar($task,lp) } {
        puts $bfh "unsetenv fev_nonlp"
    } else {
        puts $bfh "setenv fev_nonlp 1" 
    }
    close $bfh
    
}
define_proc_attributes create_inspectfev_config \
    -info "proc that creates necessary config information for inspectFV"


##################################################################
#proc	: add_vclp_waivers											
#purpose: Adding Top Down pushdown constraints
#usage	: add_vclp_waivers {design}
###################################################################
proc add_vclp_waivers { design } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "add_vclp_waivers procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global ivar env
    
}
define_proc_attributes add_vclp_waivers \
    -info "Adding VCLP Waivers"


##################################################################
#proc	: read_svf											
#purpose: proc to read svf and do some post processing 
#usage	: read_svf  
###################################################################
proc read_svf {} {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "read_svf procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global ivar env
    set task $ivar(task)
    
    if { [info exists ivar($task,read_svf_info)] && (!$ivar($task,read_svf_info)) } {
        iproc_msg -info "read_svf is disabled for this run"
        return
    }
    
    iproc_msg -info "Reading SVF file"
    
    set_svf $ivar($task,guidance_file_path)
    report_guidance -to reports
    
    if { [llength [find_svf_operation -command hier_map]] == 0 } {
        iproc_msg -warning "SVF does not contain guide_hier_map_guidance. This could lead to undesirable results"
    }

    iproc_msg -info "Stage_for_runtime_aggregation read_svf"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"
}
define_proc_attributes read_svf \
    -info "proc to read svf and do some post processing"


##################################################################
#proc	: add_blackbox_mods											
#purpose: proc to black box modules 
#usage	: add_blackbox_mods {design}   
###################################################################
proc add_blackbox_mods { design } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "add_blackbox_mods procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global env ivar
    set task $ivar(task)
    set temp_block_box_mods ""
    
    if { ![info exists ivar($task,$design,black_box)] || $ivar($task,$design,black_box) == "" } {
        iproc_msg -info "No modules found for blackboxing"
    } else {
        foreach module $ivar($task,$design,black_box) {
            set child_mod_exist [lsearch -inline -all -exact $ivar($design,child_modules) $module]
            iproc_msg -info "$child_mod_exist"
            if { $child_mod_exist == "" } {
                iproc_msg -error "$module doesnt exist in the child_modules of the design"
            } else {
                lappend temp_block_box_mods $module	
            }		
        }
    }
    if { [info exists ivar(setup,hip_lib_types_list)] && ($ivar(setup,hip_lib_types_list) ne "") } {
        set temp_block_box_mods [concat $temp_block_box_mods $ivar(setup,hip_lib_types_list)] 
    }
    
    if { $temp_block_box_mods != "" } {
        set_app_var hdlin_interface_only $temp_block_box_mods
    }

    iproc_msg -info "Stage_for_runtime_aggregation add_blackbox_mods"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"
}
define_proc_attributes add_blackbox_mods \
    -info "proc to black box modules"


##################################################################
#proc	: gen_runtime_summary 
#purpose: Generate stagewise runtime data
#usage	: gen_runtime_summary sub_task log 
###################################################################
proc gen_runtime_summary { sub_task fm_log } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "gen_runtime_summary procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global env ivar FEV_iDATA
    
    set task $ivar(task)
    
    #	set totalruntime ""
    #	set totalmem ""

    set runtime_rpt [open "./reports/${task}_runtime.rpt" w+]
    
    set w1 25
    set w2 20
    set w3 18
    set sep +-[string repeat - $w1]-+-[string repeat - $w2]-+-[string repeat - $w3]-+
    puts $runtime_rpt $sep
    puts $runtime_rpt [format "| %-*s | %-*s | %-*s | " $w1 "Stage" $w2 "Run Time(HH:MM:SS)" $w3 "Memory Usage(MB)"]
    puts $runtime_rpt $sep
    set temp 0
    set count 0
    set count1 0
    set maxlist {}
    
    set logfile [open "$fm_log" r]

    while { [gets $logfile line] >=0 } {
        if { [regexp -nocase {^\s*INTEL_INFO\s*:\s*Stage_for_runtime_aggregation (\S+)} $line match stagename] } {
            #puts "stage: $stagename"
            while { [gets $logfile line] >=0 } {
                if { [regexp {^\s*INTEL_INFO\s*:\s*Elapse_time\s*:\s*(\S+)} $line match stagetime] } {
                    #puts "stage time: $stagetime"
                    set new [expr ($stagetime-$temp)]
                    #set newround [expr { double(round(1000*$new))/1000 }]
                    set newround [expr { ceil($new) }]
                    set secs $newround
                    
                    set temp $stagetime
                    if { $count == 0 } {
                        set count $secs
                    } else {
                        set count [expr $count + $secs]
                    }
                    set hours [expr { int($secs) / 3600 }]
                    set mins  [expr { int($secs) / 60 % 60 }]
                    set secs  [expr { int($secs) % 60 }]
                    set runtime [format "%02d:%02d:%02d" $hours $mins $secs]
                    
                    set count_hours [expr { int($count) / 3600 }]
                    set count_mins  [expr { int($count) / 60 % 60 }]
                    set count_secs  [expr { int($count) % 60 }]
                    set totalruntime [format "%02d:%02d:%02d" $count_hours $count_mins $count_secs]

                    while { [gets $logfile line] >=0 } {
                        if { [regexp {^\s*INTEL_INFO\s*:\s*Memory usage\s+:\s+(\S+)\s+mB} $line match stagemem] } {
                            #puts "stage mem: $stagemem"
                            puts $runtime_rpt [format "| %*s | %*s | %*s |" $w1 $stagename $w2 $runtime $w3 $stagemem]
                            lappend maxlist $stagemem
                            break
                        }
                    }
					break
                }               
            }
        }
    }
    close $logfile

    set max [tcl::mathfunc::max {*}$maxlist]	
    puts $runtime_rpt $sep
    puts $runtime_rpt [format "| %*s | %*s | %*s |" $w1 Total $w2 $totalruntime $w3 $max]
    puts $runtime_rpt $sep
    close $runtime_rpt
   	set FEV_iDATA(i_Runtime) $totalruntime
	set FEV_iDATA(i_Runtime_secs) $count
	set FEV_iDATA(i_Memory) $max 
    iproc_msg -info "Stage_for_runtime_aggregation gen_runtime_summary"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"
    
}
define_proc_attributes gen_runtime_summary \
    -info "Generate stagewise runtime data"


##################################################################
#proc	: add_fm_clk_dop_mapping 
#purpose: Maps duplicated netlist clk dops with rtl clk dop 
#usage	: add_fm_clk_dop_mapping design 
###################################################################
proc add_fm_clk_dop_mapping { design } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "add_fm_clk_dop_mapping procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global env ivar ref impl
    set task $ivar(task)
    
    if { [info exists ivar($task,map_clk_dops)] && (!$ivar($task,map_clk_dops)) } {
        iproc_msg -info "add_fm_clk_dop_mapping is disabled for this run"
        return
    }
    
    if { [info exists ivar($task,clk_dop_map_file)] && $ivar($task,clk_dop_map_file) != "" } {
        if { [file exists $ivar($task,clk_dop_map_file)] } {
            source $ivar($task,clk_dop_map_file)
        } else {
            iproc_msg -warning "$ivar($task,clk_dop_map_file) not found" 
            return
        }	
    } else {
        iproc_msg -warning "ivar($task,clk_dop_map_file), not defined. Assuming no clk dops require mapping"
        return
    }
	annotate_trace -stop
    
    foreach {key value} [array get dop_mapping] {
		array set dop_mapping_instances_ff {}
		array set dop_mapping_instances_lat {}
        
        iproc_msg -info "RTL DOP: $key"
        current_design $ref
        set rtl_dop [get_attribute [get_cells -hierarchical -quiet -filter "full_name =~ *$key/* && is_register==true && is_techlib==true"] full_name]
		if {$rtl_dop ne ""} {
        	set rtl_dop_prims [get_attribute [get_cells "$rtl_dop/*" -quiet -filter "is_register==true && is_techlib==true"] full_name]
		} else {
			continue	
		}
       
		if {$rtl_dop_prims ne ""} { 
        	foreach inst $rtl_dop_prims {
        	    if { [regexp {\*lat\.\d+\*} $inst match] } {
					iproc_msg -info "Found LAT: $inst" 	
					lappend dop_mapping_instances_lat($match) $inst 
        	    } elseif { [regexp {\*dff\.\d+\*} $inst match] } {
					iproc_msg -info "Found DFF: $inst"
					lappend dop_mapping_instances_ff($match) $inst
        	    } else {
        	        iproc_msg -warning "unknown inst: $inst"
        	    }	
        	}
		} else {
			iproc_msg -warning "no primitives found for RTL DOP"
			continue
		}

		if {([array size dop_mapping_instances_ff] == 0) && ([array size dop_mapping_instances_lat] == 0)} {
			array unset dop_mapping_instances_ff 
			array unset dop_mapping_instances_lat
			continue
		}
        
        current_design $impl
        foreach dop $value {
            iproc_msg -info "Netlist DOP: $dop"
            set netlist_dop [get_attribute [get_cells -hierarchical -filter "full_name =~ *$dop* && is_register==true && is_techlib==true"] full_name]
			if { $netlist_dop == "" } {
				iproc_msg -warning "$dop does not exist in netlist" 
			} else { 
        		set netlist_dop_prims [get_attribute [get_cells "$dop/*" -filter "is_register==true && is_techlib==true"] full_name]
				if {$netlist_dop_prims ne ""} { 
					foreach inst $netlist_dop_prims {
					    if { [regexp {\*lat\.\d+\*} $inst match] } {
							iproc_msg -info "Found LAT: $inst"
							lappend dop_mapping_instances_lat($match) $inst
					    } elseif { [regexp {\*dff\.\d+\*} $inst match] } {
							iproc_msg -info "Found DFF: $inst"
							lappend dop_mapping_instances_ff($match) $inst
					    } else {
					        iproc_msg -warning "unknown inst: $inst"
					    }	
					}
				} else {
					iproc_msg -warning "no primitives found for Netlist DOP"
				}
            }
		}

		foreach {key value} [array get dop_mapping_instances_ff] {
			if {[llength $value] > 1 } {
				set command "set_user_match $value"
				#iproc_msg -info "Command: $command"
				eval $command
			}
		}

		foreach {key value} [array get dop_mapping_instances_lat] {
			if {[llength $value] > 1 } {
				set command "set_user_match $value"
				#iproc_msg -info "Command: $command"
				eval $command
			}
		}

		array unset dop_mapping_instances_ff 
		array unset dop_mapping_instances_lat

    }
	iproc_msg -info "Stage_for_runtime_aggregation add_fm_clk_dop_mapping"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"
	annotate_trace -start    
}
define_proc_attributes add_fm_clk_dop_mapping \
    -info "Maps duplicated netlist clk dops with rtl clk dop"


################################################################################
#proc   : generate_indicator_stats                                          
#purpose: For generating the indicator 
#usage  : generate_indicator_stats design stats_file
################################################################################
proc generate_indicator_stats { design stats_file } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "generate_indicator_stats procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global env ivar FEV_iDATA
    set task $ivar(task)
    set lp_err 0
    
   	annotate_trace -stop
    
    if { [file exists $stats_file] } {
        file delete -force $stats_file
    }	
    if { [catch { set SFH [open $stats_file w] } errMsg] } {
        iproc_msg -error "$errMsg"
        return
    } else {
        iproc_msg -info "Creating the indicator data @ $stats_file"
    }
    puts $SFH "array set FEV_iDATA {}"
    set FEV_iDATA(i_Run_dir) $env(PWD)
    if { [info exists ivar($task,lp)] && $ivar($task,lp) && [info exists ivar($task,enable_compare_lp)] && $ivar($task,enable_compare_lp) } {
        set FEV_iDATA(i_Lowpower) 1
    } else {
        set FEV_iDATA(i_Lowpower) 0
    }
	
    set FEV_iDATA(i_Formality_version) [ lindex [get_app_var sh_product_version ] 0]
    set FEV_iDATA(i_VCLP_version) [file tail [get_unix_variable VC_STATIC_HOME]]
    if { [info exists ivar(pdk_dir) ] } {
	    set FEV_iDATA(i_PDK_dir) $ivar(pdk_dir)
    } else {
		set FEV_iDATA(i_PDK_dir) "NA"
	}
			
	if {[catch {set lib_version [get_lib_version_for_indicator]} errorMsg]} {
		iproc_msg -warning "Error Occured in proc call get_lib_version_for_indicator" 
        set FEV_iDATA(i_Std_cell_version) "NA"
    } else {
      	iproc_msg -info "Creating the indicator data for std_cell_version"
        set FEV_iDATA(i_Std_cell_version) $lib_version
	}
    set FEV_iDATA(i_Failing) [llength [ report_failing_points -list]]
    set FEV_iDATA(i_Passing) [llength [ report_passing_points -list]]
    set FEV_iDATA(i_Abort) [llength [ report_aborted_points -list]]
    set FEV_iDATA(i_Unverified) [llength [ report_unverified_points -list]]
	set FEV_iDATA(i_Unmatched) [llength [ report_unmatched_points -list]]
	set FEV_iDATA(i_Matched) [llength [ report_matched_points -list ]]

	set FEV_iDATA(i_Signature_match) [llength [ report_matched_points -list -method function]]
	set FEV_iDATA(i_Name_match) [llength [ report_matched_points -list -method name]]
	set FEV_iDATA(i_Topology_match) [llength [ report_matched_points -list -method topology]]
	set FEV_iDATA(i_User_match) [llength [ report_matched_points -list -method user]]

	set FEV_iDATA(i_Bbox_match) [llength [ report_matched_points -list -point_type bbox]]
	set FEV_iDATA(i_Bboxes_unmatch_R) [llength [ report_unmatched_points -list -reference -point_type bbox]]
	set FEV_iDATA(i_Bboxex_unmatch_I) [llength [ report_unmatched_points -list -implementation -point_type bbox]]
	set FEV_iDATA(i_Unmatch_unread_R) [llength [ report_unmatched_points -list -reference -status unread]]
	set FEV_iDATA(i_Unmatch_unread_I) [llength [ report_unmatched_points -list -implementation -status unread]]
    
    if { [info exists ivar($task,lp)] && $ivar($task,lp) && [info exists ivar($task,enable_compare_lp)] && $ivar($task,enable_compare_lp) } {
        set r_file reports/$design.lp_violations.rpt
        if { [file exists $r_file] } {
            set report_file [open $r_file r]
            while { [gets $report_file line] >=0 } {
                if { [regexp {^\s+Total\s+(\d+)\s+(\d+)\s+(\d+)(\s+)?(\d+)?} $line match error_cnt warn_cnt info_cnt spc waived_cnt] } {
                    set lp_err $error_cnt
                }
                if { [regexp {^\s+warning\s+UPF\s+DIFF_PSW_LOGIC\s+(\d+)} $line -> psw_cnt] } {
                    set lp_err [expr {$error_cnt + $psw_cnt}]
                }
            }	
            set FEV_iDATA(i_LP_VIOL) $lp_err
            close $report_file
        } else {
            iproc_msg -warning "$design.lp_violations.rpt is not available, check VCLP status"
        }
        
    }	
    foreach metrics [array names FEV_iDATA] {
        puts $SFH "set FEV_iDATA($metrics) $FEV_iDATA($metrics)"
    }
    close $SFH

    iproc_msg -info "Stage_for_runtime_aggregation generate_indicator_stats"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"

	annotate_trace -start
    
}
define_proc_attributes generate_indicator_stats \
    -info "For generating the indicator"


################################################################################
#proc   : generate_indicator_fm_eco                                          
#purpose: For generating the indicator in fm ECO runs, 
#usage  : generate_indicator_stats design stats_file
################################################################################
proc generate_indicator_fm_eco { location stats_file { fm_log "" } } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "generate_indicator_fm_eco procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global env ivar FEV_iDATA
    set task $ivar(task)
    
    set mode ""
    if { $task == "eco_pre_synth" } {
        set mode "pre"
    } elseif { $task == "eco_post_synth" }  {
        set mode "post"
    } elseif { $task == "eco_confirm_patch" } {
        set mode "patch"
    }
    
    
    if { [file exists $stats_file] } {
        puts "file found"
        file delete -force $stats_file
    }	

    if { [catch { set SFH [open $stats_file w] } errMsg] } {
        iproc_msg -error "$errMsg"
        return
    } else {
        iproc_msg -info "Creating the indicator data @ $stats_file"
    }

    puts $SFH "array set FEV_iDATA {}"

    ## Start processing indicator items

    # case 1 -> parse through logfile to get regions info
    if { $location == "regions" && $fm_log ne "" } {
        set logfile [open "$fm_log" r]
        set found 0
        while { [gets $logfile line] >=0 } {
            if { $found == "0" && [regexp {^Find ECO regions: Found\s+(\d+)\s+ECO regions} $line -> region_cnt ] } {
                set FEV_iDATA(i_ECO_Regions_cnt) $region_cnt
                set found 1
            }
            if { [regexp {^Find ECO regions: Structural analysis found (\d+) rewiring ECOs} $line -> rewire_cnt ] } {
                set FEV_iDATA(i_ECO_Regions_rewiring) $rewire_cnt
            }
            if { [regexp {^Match ECO regions: Matched (\d+) ECO regions} $line -> match_cnt ] } {
                set FEV_iDATA(i_ECO_Regions_match) $match_cnt
                break
            }
        }
        close $logfile
    }

    # case 2 -> verify in all 3 templates
    if { $location == "verify" } {
        set FEV_iDATA(i_${mode}_ECO_Failing) [llength [ report_failing_points -list]]
        set FEV_iDATA(i_${mode}_ECO_Passing) [llength [ report_passing_points -list]]
        set FEV_iDATA(i_${mode}_ECO_Abort) [llength [ report_aborted_points -list]]
        set FEV_iDATA(i_${mode}_ECO_Unverified) [llength [ report_unverified_points -list]]
        set FEV_iDATA(i_${mode}_ECO_Unmatched) [llength [ report_unmatched_points -list]]
        set FEV_iDATA(i_${mode}_ECO_Matched) [llength [ report_matched_points -list ]]

        set FEV_iDATA(i_${mode}_ECO_Signature_match) [llength [ report_matched_points -list -method function]]
        set FEV_iDATA(i_${mode}_ECO_Name_match) [llength [ report_matched_points -list -method name]]
        set FEV_iDATA(i_${mode}_ECO_Topology_match) [llength [ report_matched_points -list -method topology]]
        set FEV_iDATA(i_${mode}_ECO_User_match) [llength [ report_matched_points -list -method user]]

        set FEV_iDATA(i_${mode}_ECO_Bbox_match) [llength [ report_matched_points -list -point_type bbox]]
        set FEV_iDATA(i_${mode}_ECO_Bboxes_unmatch_R) [llength [ report_unmatched_points -list -reference -point_type bbox]]
        set FEV_iDATA(i_${mode}_ECO_Bboxex_unmatch_I) [llength [ report_unmatched_points -list -implementation -point_type bbox]]
        set FEV_iDATA(i_${mode}_ECO_Unmatch_unread_R) [llength [ report_unmatched_points -list -reference -status unread]]
        set FEV_iDATA(i_${mode}_ECO_Unmatch_unread_I) [llength [ report_unmatched_points -list -implementation -status unread]]
    }

    # case 3 -> eco_pre_synth or eco_post_synth after  create_eco_patch command
    if { $location == "eco_impact" } {
        redirect -variable eco_impact "report_eco_impact -size"
        set eco_impact_lines [split $eco_impact "\n"]
        set type ""
        
        # defaulting to 0
        set FEV_iDATA(i_ECO_Added_total_cells) 0
        set FEV_iDATA(i_ECO_Added_total_nets) 0
        set FEV_iDATA(i_ECO_Added_total_ports) 0
        set FEV_iDATA(i_ECO_Removed_total_cells) 0
        set FEV_iDATA(i_ECO_Removed_total_nets) 0
        set FEV_iDATA(i_ECO_Removed_total_ports) 0

        set FEV_iDATA(i_ECO_Added_buffers/inverters) 0
        set FEV_iDATA(i_ECO_Added_combinational) 0
        set FEV_iDATA(i_ECO_Added_sequential) 0
        #set FEV_iDATA(i_ECO_Added_total) 0
        set FEV_iDATA(i_ECO_Removed_buffers/inverters) 0
        set FEV_iDATA(i_ECO_Removed_combinational) 0
        set FEV_iDATA(i_ECO_Removed_sequential) 0
        #set FEV_iDATA(i_ECO_Removed_total) 0

        foreach line $eco_impact_lines {

            # for added info
            if { [regexp {introduces( (\d+) cells)?(, (\d+) nets)?(, (\d+) ports)?} $line -> - cells - nets - ports] } {
                if { $cells ne "" } {
                    set FEV_iDATA(i_ECO_Added_total_cells) $cells
                }
                if { $nets ne "" } {
                    set FEV_iDATA(i_ECO_Added_total_nets) $nets
                } 
                if { $ports ne "" } {
                    set FEV_iDATA(i_ECO_Added_total_ports) $ports
                } 
            }

            # for removes info
            if { [regexp {removes( (\d+) cells)?(, (\d+) nets)?(, (\d+) ports)?} $line -> - cells - nets - ports] } {
                if { $cells ne "" } {
                    set FEV_iDATA(i_ECO_Removed_total_cells) $cells
                }
                if { $nets ne "" } {
                    set FEV_iDATA(i_ECO_Removed_total_nets) $nets
                } 
                if { $ports ne "" } {
                    set FEV_iDATA(i_ECO_Removed_total_ports) $ports
                } 
            }


            if { [regexp {\s+Added cells} $line -> cells nets ports] } {
                set type "Added"
            }
            if { [regexp {\s+Removed cells} $line -> cells nets ports] } {
                set type "Removed"
            }
            if { $type ne "" && [regexp {^\s+(\S+):\s+(\d+)} $line -> name count] } {
                if { $name ne "total" } {
                    set FEV_iDATA(i_ECO_${type}_${name}) $count
                }
            }
        }
    }

    # case 4 -> eco_post_synth and after  match_post_eco
    if { $location == "match" } {
        set FEV_iDATA(i_${mode}_ECO_Unmatched) [llength [ report_unmatched_points -list]]
        set FEV_iDATA(i_${mode}_ECO_Matched) [llength [ report_matched_points -list ]]

        set FEV_iDATA(i_${mode}_ECO_Signature_match) [llength [ report_matched_points -list -method function]]
        set FEV_iDATA(i_${mode}_ECO_Name_match) [llength [ report_matched_points -list -method name]]
        set FEV_iDATA(i_${mode}_ECO_Topology_match) [llength [ report_matched_points -list -method topology]]
        set FEV_iDATA(i_${mode}_ECO_User_match) [llength [ report_matched_points -list -method user]]

        set FEV_iDATA(i_${mode}_ECO_Bbox_match) [llength [ report_matched_points -list -point_type bbox]]
        set FEV_iDATA(i_${mode}_ECO_Bboxes_unmatch_R) [llength [ report_unmatched_points -list -reference -point_type bbox]]
        set FEV_iDATA(i_${mode}_ECO_Bboxex_unmatch_I) [llength [ report_unmatched_points -list -implementation -point_type bbox]]
        set FEV_iDATA(i_${mode}_ECO_Unmatch_unread_R) [llength [ report_unmatched_points -list -reference -status unread]]
        set FEV_iDATA(i_${mode}_ECO_Unmatch_unread_I) [llength [ report_unmatched_points -list -implementation -status unread]]
    }


    # general case 
    if { $location == "general" } {
        set FEV_iDATA(i_Run_dir) $env(PWD)
        set FEV_iDATA(i_Formality_version) [ lindex [get_app_var sh_product_version ] 0]
        set FEV_iDATA(i_VCLP_version) [file tail [get_unix_variable VC_STATIC_HOME]]
    if { [info exists ivar(pdk_dir) ] } {
	    set FEV_iDATA(i_PDK_dir) $ivar(pdk_dir)
    } else {
		set FEV_iDATA(i_PDK_dir) "NA"
	}
			
	if {[catch {set lib_version [get_lib_version_for_indicator]} errorMsg]} {
		iproc_msg -warning "Error Occured in proc call get_lib_version_for_indicator" 
        set FEV_iDATA(i_Std_cell_version) "NA"
    } else {
      	iproc_msg -info "Creating the indicator data for std_cell_version"
        set FEV_iDATA(i_Std_cell_version) $lib_version
	}
        # ECO has target switch only, so upf will always be 0.
        # if { [info exists ivar($task,lp)] && $ivar($task,lp) && [info exists ivar($task,enable_compare_lp)] && $ivar($task,enable_compare_lp) } {
        #     set FEV_iDATA(i_Lowpower) 1
        # } else {
        set FEV_iDATA(i_Lowpower) 0
        # }
    }

    # dumps the fev_idata Info into file
    foreach metrics [array names FEV_iDATA] {
        puts $SFH "set FEV_iDATA($metrics) $FEV_iDATA($metrics)"
    }

    close $SFH

    iproc_msg -info "Stage_for_runtime_aggregation generate_indicator_fm_eco"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"

}
define_proc_attributes generate_indicator_fm_eco \
    -info "For generating the indicator in ECO run"


################################################################################
#proc   : generate_indicator_stats_lite
#purpose: For generating the indicator for fev_fm_lite
#usage  : generate_indicator_stats_lite design stats_file fm_log
################################################################################
proc generate_indicator_stats_lite { design stats_file { fm_log "" } } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "generate_indicator_stats_lite procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    global env ivar FEV_iDATA
    set task $ivar(task)
    annotate_trace -stop

    if { [file exists $stats_file] } {
        file delete -force $stats_file
    }

    if { [catch { set SFH [open $stats_file w] } errMsg] } {
        iproc_msg -error "$errMsg"
        return
    } else {
        iproc_msg -info "Creating the indicator data @ $stats_file"
    }

    puts $SFH "array set FEV_iDATA {}"

    set FEV_iDATA(i_Run_dir) $env(PWD)

    if { [info exists ivar($task,lp)] && $ivar($task,lp) && [info exists ivar($task,enable_compare_lp)] && $ivar($task,enable_compare_lp) } {
        set FEV_iDATA(i_Lowpower) 1
    } else {
        set FEV_iDATA(i_Lowpower) 0
    }
    
    set FEV_iDATA(i_Formality_version) [ lindex [get_app_var sh_product_version ] 0]
    set FEV_iDATA(i_VCLP_version) [file tail [get_unix_variable VC_STATIC_HOME]]

    if { [info exists ivar(pdk_dir) ] } {
        set FEV_iDATA(i_PDK_dir) $ivar(pdk_dir)
    } else {
        set FEV_iDATA(i_PDK_dir) "NA"
    }

    #TODO :fev_lite completed successfully -fail/success
            
    if {[catch {set lib_version [get_lib_version_for_indicator]} errorMsg]} {
        iproc_msg -warning "Error Occured in proc call get_lib_version_for_indicator" 
        set FEV_iDATA(i_Std_cell_version) "NA"
    } else {
        iproc_msg -info "Creating the indicator data for std_cell_version"
        set FEV_iDATA(i_Std_cell_version) $lib_version
    }

    set FEV_iDATA(i_FEV_RTL_Undrivens) [llength [report_unmatched_points -status undriven -point_type cut -reference -list]]
    
    # Parse RTL_seq_const report to extract constantx register count
    set rtl_seq_const_rpt "$env(PWD)/reports/$design.RTL_seq_constx.rpt"
    if { [file exists $rtl_seq_const_rpt] } {
        set rpt_file [open $rtl_seq_const_rpt r]
        while { [gets $rpt_file line] >= 0 } {
            if { [regexp {^\s*(\d+)\s+constantx registers:} $line -> const_count] } {
                set FEV_iDATA(i_FEV_RTL_seq_const) $const_count
                break
            }
        }
        close $rpt_file
    } else {
        iproc_msg -warning "RTL_seq_const report file $rtl_seq_const_rpt not found"
        set FEV_iDATA(i_FEV_RTL_seq_const) "NA"
    }

    # process for log's matching results
    if { [file exists $fm_log] } {
        set logfile [open "$fm_log" r]
        while { [gets $logfile line] >= 0 } {
            # Look for the header line that starts the "Unmatched Objects" table
            if { [regexp {^\s*Unmatched Objects\s+REF\s+IMPL} $line] } {
                # Skip the separator line that follows
                gets $logfile line
                # Now process each entry line until we hit the line of asterisks
                while { [gets $logfile line] >= 0 } {
                    # Stop when reaching the row of asterisks or an empty line
                    if { [regexp {^\*+} $line] || [string trim $line] eq "" } {
                        break
                    }
                    if { [regexp {^\s*([^0-9].*?)\s+([0-9]+)\s+([0-9]+)\s*$} $line -> raw_name ref_cnt impl_cnt] } {
                        # 1) Remove anything in parentheses:
                        regsub -all {\([^)]*\)} $raw_name "" clean_name
                        # 2) Trim whitespace:
                        set clean_name [string trim $clean_name]
                        # 3) Convert "-" to "_":
                        regsub -all {\-} $clean_name "_" clean_name
                        # 4) Convert spaces (one or more) to single "_":
                        regsub -all {\s+} $clean_name "_" clean_name

                        # Store only the REF column value for each processed row
                        set FEV_iDATA(i_${clean_name}) $ref_cnt
                    }
                }
                # Break out of the outer loop once the table is processed
                break
            }
        }
        close $logfile
    } else {
        iproc_msg -warning "Log file $fm_log not found, skipping log parsing."
    }


    foreach metrics [array names FEV_iDATA] {
        puts $SFH "set FEV_iDATA($metrics) $FEV_iDATA($metrics)"
    }

    close $SFH
    iproc_msg -info "Stage_for_runtime_aggregation generate_indicator_stats_lite"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"

    annotate_trace -start
}
define_proc_attributes generate_indicator_stats_lite \
    -info "For generating the indicator for fev_fm_lite"


################################################################################
#proc   : read_dummy_gate                                          
#purpose: Used for generating dummy netlist used in fev_fm_lite runs 
#usage  : read_dummy_gate netlist_path root_module container 
################################################################################
proc read_dummy_gate { netlist_path root_module container } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "read_dummy_gate is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global env ivar
    
    if { [file exists $netlist_path] } {
        file delete -force $netlist_path
    }	
    
    set bfh [open $netlist_path w]
    puts $bfh "module ${root_module}(i,o);"
    puts $bfh "input i;" 
    puts $bfh "output o;"
    puts $bfh "assign o = i;"
    puts $bfh "endmodule"
    close $bfh
    
    puts "fm_command: read_sverilog -$container $netlist_path"
    read_sverilog -$container $netlist_path
    if { ![set_top $container:/*/$root_module] } {
		iproc_msg -error "set_top failed"
		exit -1
	}
    iproc_msg -info "Stage_for_runtime_aggregation read_dummy_gate"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"
    
}
define_proc_attributes read_dummy_gate \
    -info "Used for generating dummy netlist used in fev_fm_lite runs"


################################################################################
#proc   : check_metaflop_settings                                          
#purpose: Applies settings for Metaflop checking 
#usage  : check_metaflop_settings variant design 
################################################################################
proc check_metaflop_settings { variant design } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "check_metaflop_settings procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
	global env ivar ref impl
    set task $ivar(task)

	if { [info exists ivar($task,enable_meta_check)] && (!$ivar($task,enable_meta_check)) } {
        iproc_msg -info "check_metaflop_settings is disabled for this run"
        return
    }

	annotate_trace -stop
	set all_lib_cells ""

	if { ![info exists ivar($task,metaflop_pattrn_rtl)] || $ivar($task,metaflop_pattrn_rtl) eq "" } {
    	iproc_msg -warning "No pattern found for metaflops in RTL"
    } else {	
		foreach pattern $ivar($task,metaflop_pattrn_rtl) {
			lappend all_lib_cells [get_lib_cells -quiet r:/*/$pattern]
			lappend all_lib_cells [get_lib_cells -quiet i:/*/$pattern] 
		}
    }

    if { ![info exists ivar($task,metaflop_pattrn_gate)] || $ivar($task,metaflop_pattrn_gate) eq "" } {
    	iproc_msg -warning "No pattern found for metaflops in Netlist"
    } else {	
		foreach pattern $ivar($task,metaflop_pattrn_gate) {
			lappend all_lib_cells [get_lib_cells -quiet r:/*/$pattern]
			lappend all_lib_cells [get_lib_cells -quiet i:/*/$pattern] 
		}
    }	
	
	if { $all_lib_cells eq "" } {
		iproc_msg -warning "No Metaflop cells found"
		annotate_trace -start
		return
	}	

	set_cell_type -value synchronizer $all_lib_cells
	

	if { [info exists ivar($task,seq_const_check)] && $ivar($task,seq_const_check) } {
		set_cell_type -value reg_init_none $all_lib_cells	
	}

	if { [info exists ivar($task,verify_unread_meta)] && $ivar($task,verify_unread_meta) } {
		set_cell_type -value verify_unread $all_lib_cells	
	}
	iproc_msg -info "Stage_for_runtime_aggregation check_metaflop_settings"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"
	annotate_trace -start	
}
define_proc_attributes check_metaflop_settings \
    -info "Applies settings for Metaflop checking"


################################################################################
#proc   : check_metaflop                                          
#purpose: Checks if Metaflops are not merged and duplicated 
#usage  : check_metaflop variant design 
################################################################################
proc check_metaflop { variant design } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "check_metaflop procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################

    global env ivar ref impl
    set task $ivar(task)

	if { [info exists ivar($task,enable_meta_check)] && (!$ivar($task,enable_meta_check)) } {
        iproc_msg -info "check_metaflop is disabled for this run"
        return
    }

	iproc_msg -info "Checking Metaflops"

	annotate_trace -stop

    set r_all_metaflops ""
    set i_all_metaflops ""
	set meta_rpt "./reports/$design.metaflop_verif.rpt"
	set rfh [open $meta_rpt w]


	#Get all Metaflops in design
    if { [info exists ivar($task,metaflop_pattrn_gate)] && $ivar($task,metaflop_pattrn_gate) != "" } {

		set references_filter [join [lmap x $ivar($task,metaflop_pattrn_gate) {string cat "r:/*/" ${x}}]]
		current_design $ref
		set r_metaflop [get_cells -hierarchical -of_references $references_filter]
		
		# build list of SEQs inside techlib-cell instances
		if { [sizeof_collection $r_metaflop] > 0 } {
			array unset libcell_seqs
			array set libcell_seqs ""
			# build array of SEQ names inside each libcell
			foreach_in_collection libcell [get_lib_cells $references_filter] {
				set libcell_seqs([get_attribute $libcell name]) [get_attribute [get_cells -quiet [get_attribute $libcell full_name]/* -filter "ref_name==SEQ"] name]
			}
			foreach_in_collection cell $r_metaflop {
				set libcell [get_attribute $cell ref_name]
				if { [llength libcell_seqs($libcell)] == 0 } {
					iproc_msg -warning "no SEQs inside instances of metaflop libcell $libcell; skipping."
					continue
				} else {
					set instance_name [get_attribute $cell full_name]
					foreach seq $libcell_seqs($libcell) {
						lappend r_all_metaflops $instance_name/$seq
					}
				}
			}  
		}

		set implementation_filter [join [lmap x $ivar($task,metaflop_pattrn_gate) {string cat "i:/*/" ${x}}]]
		current_design $impl
		set i_metaflop [get_cells -hierarchical -of_references $implementation_filter]
		
		# build list of SEQs inside techlib-cell instances
		if { [sizeof_collection $i_metaflop] > 0 } {
			array unset libcell_seqs
			array set libcell_seqs ""
			# build array of SEQ names inside each libcell
			foreach_in_collection libcell [get_lib_cells $implementation_filter] {
				set libcell_seqs([get_attribute $libcell name]) [get_attribute [get_cells -quiet [get_attribute $libcell full_name]/* -filter "ref_name==SEQ"] name]
			}
			foreach_in_collection cell $i_metaflop {
				set libcell [get_attribute $cell ref_name]
				if { [llength libcell_seqs($libcell)] == 0 } {
					iproc_msg -warning "no SEQs inside instances of metaflop libcell $libcell; skipping."
					continue
				} else {
					set instance_name [get_attribute $cell full_name]
					foreach seq $libcell_seqs($libcell) {
						lappend i_all_metaflops $instance_name/$seq
					}
				}
			}  
		}
    }

    if { [info exists ivar($task,metaflop_pattrn_rtl)] && $ivar($task,metaflop_pattrn_rtl) != "" } {
    	set full_name_filter [join [lmap x $ivar($task,metaflop_pattrn_rtl) {string cat "full_name=~" ${x}}] " || "]
    	set full_name_cmd "get_cells -hierarchical -filter \"(($full_name_filter) && is_register==true && cell_type==SEQ)\""

		#Find Metaflops in ref using rtl pattern
    	current_design $ref
    	set r_metaflop [get_attribute [eval $full_name_cmd] full_name]
    	if { [llength $r_metaflop] > 0 } {
    		set r_all_metaflops [lsort -unique [concat $r_all_metaflops $r_metaflop]]
    	}

		#Find Metaflops in impl using rtl pattern
    	current_design $impl
    	set i_metaflop [get_attribute [eval $full_name_cmd] full_name]
    	if { [llength $i_metaflop] > 0 } {
    		set i_all_metaflops [lsort -unique [concat $i_all_metaflops $i_metaflop]]
    	}
    }

	#Catch metaflops that were merged through SVF
    set cmd "report_svf_operation -status accepted -command {reg_merging}"
    redirect -variable merge_svf_info {eval $cmd}
    set merge_svf_info_lines [split $merge_svf_info "\n"]
	foreach line $merge_svf_info_lines {
		if { [string match "*-from*" $line] } {
			regsub {\s*-from\s*\{} $line "" line
			regsub {\s*\}\s*\\} $line "" line
			foreach reg $line {
				if { [string match "*$reg*" $r_all_metaflops] } {
					iproc_msg -info "guide_reg_merging found on Metaflop $reg"
					puts $rfh "INTEL_ERROR  : guide_reg_merging found on Metaflop $reg"
				}
			}
		}
	}

	##Check if user applied any 1 to N matches
	array set match_array ""
	foreach match [report_matched_points -list] {
		lappend match_array([lindex $match 0]) [lindex $match 1]
	}
	foreach match [array names match_array] {
		if { [llength $match_array($match)] >= 2 } {
			foreach temp $match_array($match)	{
				if { [string match "*$temp*" $i_all_metaflops] } {
					iproc_msg -info "1 to N matching found on Metaflop $temp"
					puts $rfh "INTEL_ERROR  : 1 to N matching found on Metaflop $temp"
				}
			}
		}
	}

	#Check if Metaflop is matched with other metaflops
	#Create matched database into hash
	array set all_matched_array ""
	foreach match [report_matched_points -list] {
		foreach item $match {
			regsub -all {\\} $item "" item
			lappend all_matched_array($item) ""
		}
	}
	#iproc_msg -info "# Matched points: [array size all_matched_array]"  
	
	#Create matched meta database into hash
	array set meta_matched_array ""
	#temporarily using reg_init_none, should really be synchonizer, need to talk to SNPS
	foreach match [report_matched_points -cell_type reg_init_none -list] {
		foreach item $match {
			regsub -all {\\} $item "" item
			lappend meta_matched_array($item) ""
		}
	}
	#iproc_msg -info "# Meta Matched points: [array size meta_matched_array]"

	#Checking ref meta
	foreach cell $r_all_metaflops {
		#Check to see if it is matched
		if { [info exists all_matched_array($cell)] } {
			#check to see if it is matched to another meta
			if { ![info exists meta_matched_array($cell)] } {
				iproc_msg -info "Metaflop $cell not matched to metaflop instance in impl"
				puts $rfh "INTEL_ERROR  : Metaflop $cell not matched to metaflop instance in impl"
			}
		}
	}

	#Checking impl meta
	foreach cell $i_all_metaflops {
		#Check to see if it is matched
		if { [info exists all_matched_array($cell)] } {
			#check to see if it is matched to another meta
			if { ![info exists meta_matched_array($cell)] } {
				iproc_msg -info "Metaflop $cell not matched to metaflop instance in ref"
				puts $rfh "INTEL_ERROR  : Metaflop $cell not matched to metaflop instance in ref"
			}
		}
	}

	if { [info exists ivar($task,verify_unread_meta)] && $ivar($task,verify_unread_meta) } {

		#check which metaflops have been succesfully verified either pass/fail
    	set r_verified_cells ""
    	set r_unverified_cells ""
    	set i_verified_cells ""
    	set i_unverified_cells ""
		array set pass_fail_hash {}

		foreach pass [report_passing_points -list] {
			foreach item $pass {
				regsub -all {\\} $item "" item
				lappend pass_fail_hash($item) ""
			}
		}

		foreach fail [report_failing_points -list] {
			foreach item $fail {
				regsub -all {\\} $item "" item
				lappend pass_fail_hash($item) ""
			}			
		}

		foreach cell $r_all_metaflops {
			#iproc_msg -info "cell r: $cell"
			if { [info exists pass_fail_hash($cell)] } {
				#puts "found"
				lappend r_verified_cells $cell
			} else {
				#puts "not found"
				iproc_msg -info "Metaflop $cell was not verified"
				puts $rfh "INTEL_ERROR  : Metaflop $cell was not verified"
				lappend r_unverified_cells $cell
			}
		}
		
		foreach cell $i_all_metaflops {
			#iproc_msg -info "cell i: $cell"
			if { [info exists pass_fail_hash($cell)] } {
				#puts "found"
				lappend i_verified_cells $cell
			} else {
				#puts "not found"
				iproc_msg -info "Metaflop $cell was not verified"
				puts $rfh "INTEL_ERROR  : Metaflop $cell was not verified"
		 		lappend i_unverified_cells $cell
			}
		}	

		iproc_msg -info "# of ref Metaflops: [llength $r_all_metaflops]"
		iproc_msg -info "# of verified ref Metaflops: [llength $r_verified_cells]"
		iproc_msg -info "# of unverified ref Metaflops: [llength $r_unverified_cells]"
		iproc_msg -info "# of impl Metaflops: [llength $i_all_metaflops]"
		iproc_msg -info "# of verified impl Metaflops: [llength $i_verified_cells]"
		iproc_msg -info "# of unverified impl Metaflops: [llength $i_unverified_cells]"

	}
    iproc_msg -info "Stage_for_runtime_aggregation check_metaflop"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"

	annotate_trace -start

	close $rfh
}
define_proc_attributes check_metaflop \
    -info "Checks if Metaflops are not merged and duplicated"


################################################################################
#proc   : insertBBCutAtOutput                                          
#purpose: Inserts black box cut points at output of unverified flops 
#usage  : insertBBCutAtOutput cells 
################################################################################
proc insertBBCutAtOutput { cells } {

	set cutSuffix "metaflopCutBB"
	set saveCurrentDesign [current_design]
	
	foreach_in_collection c $cells {
	        current_design  [get_attribute $c parent_name]
	        set cellName [get_attribute $c name]
	
	        ## if the cut already exists do not insert another cut
	        set checkCell [get_cells ${cellName}${cutSuffix} -quiet]
	
	        if { [sizeof_collection $checkCell] == 0 } {
					iproc_msg -info "Creating blackbox cutpoint at ${cellName}${cutSuffix}" 
	                create_cutpoint_blackbox  ${cellName}${cutSuffix} -type pin  ${cellName}/o  
	        }
	
	}
	current_design $saveCurrentDesign
}
define_proc_attributes insertBBCutAtOutput \
    -info "Inserts black box cut points at output of unverified flops"


################################################################################
#proc   : modify_search_path                                                                                    
#purpose: proc to change the search_paths for fev 
#usage  : modify_search_path  
################################################################################
proc modify_search_path {} {
        ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
        iproc_msg -info "modify_search_path procedure is invoked from file: [lindex [info frame 6] 5]"
        #################################################################################

        global env ivar
        set task $ivar(task)

        set remove [list ./scripts $ivar(bscript_dir) $ivar(fscript_dir)]
        set tmp "$ivar(search_path)"
        foreach a $remove {
            set item_to_remove [lsearch $tmp $a]
            set tmp [lreplace $tmp $item_to_remove $item_to_remove ]
        }
        set ivar(search_path) "$tmp"
        set ivar(search_path) [ linsert $ivar(search_path) 0 $ivar(bscript_dir) ]
        set ivar(search_path) [ linsert $ivar(search_path) 0 $ivar(bscript_dir)/$task ]
        set ivar(search_path) [ linsert $ivar(search_path) 0 $ivar(fscript_dir) ]
        set ivar(search_path) [ linsert $ivar(search_path) 0 $ivar(fscript_dir)/$task ]
        set ivar(search_path) [ linsert $ivar(search_path) 0 ./scripts ]

}
define_proc_attributes modify_search_path \
    -info "Modifies search path to ensure search priority is upheld"

################################################################################
#proc	: fev_setup_commands										
#purpose: proc to add setup commands for fev 
#usage	: fev_setup_commands 
#################################################################################
proc fev_setup_commands {} {
	######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
	iproc_msg -info "fev_setup_commands procedure is invoked from file: [lindex [info frame 6] 5]"
	##################################################################################
	
	global env ivar
	set task $ivar(task)

    ## diamond CALL
	set curr_tool "formality"
    #---- usage of version is optional (based on tool specifics)
	set curr_ver [exec cth_query toolversion formality]
    set fm_path ""
	if { [info exists ivar($task,fm_path) ] && ( $ivar($task,fm_path) ne "" ) } {
        regsub -all {\/\/} $ivar($task,fm_path) "\/" fm_path
		regexp {/([^/]+)/[^/]+/[^/]+$} $fm_path -> extracted
		set curr_ver $extracted

	}
   	set dsv [exec cth_query params cth2_ver]
   	set diamond_script "/usr/intel/bin/dts_register"
   	set is_disable 0
	if {[info exists ivar(DISABLE_DIAMOND)] && $ivar(DISABLE_DIAMOND)==1} {
     	set is_disable 1
   	}
   
	if {[file exists $diamond_script] && [file readable $diamond_script]} {
		if {$is_disable==0} {

    	    iproc_msg -info "Executing: $diamond_script -tool=$curr_tool -version=$curr_ver -ds Cheetah -dsv $dsv"

    	    if {[catch {exec $diamond_script -tool=$curr_tool -version=$curr_ver -ds Cheetah -dsv $dsv} err]} {

        	    iproc_msg -error "Diamond failed with message: $err"
        	}

		} else {
        	iproc_msg -info "Diamond is disabled as ivar(DISABLE_DIAMOND)=$ivar(DISABLE_DIAMOND)"
      	}
	} else {
    	iproc_msg -error "Script $diamond_script does not exist or not readable"
   }

	# dotf settings
	if { [info exists ivar($task,read_rtl_proc_golden)] && $ivar($task,read_rtl_proc_golden) == "" } {
		if { [info exists ivar(rtl,rtl_type)] && $ivar(rtl,rtl_type) == "dotf" } {
			set ivar($task,read_rtl_proc_golden) "read_rtl_dotf" 
			set ivar($task,rtl_list_golden) $ivar($task,rtl_list_f_golden)
		} else {
			set ivar($task,read_rtl_proc_golden) "read_rtl_2stage" 
		}
	}
	if { [info exists ivar($task,read_rtl_proc_revised)] && $ivar($task,read_rtl_proc_revised) == "" } {
		if { [info exists ivar(rtl,rtl_type)] && $ivar(rtl,rtl_type) == "dotf" } {
			set ivar($task,read_rtl_proc_revised) "read_rtl_dotf" 
			set ivar($task,rtl_list_revised) $ivar($task,rtl_list_f_revised)
		} else {
			set ivar($task,read_rtl_proc_revised) "read_rtl_2stage" 
		}
	}

}    
define_proc_attributes fev_setup_commands \
    -info "proc to add setup commands for fev"

################################################################################
#proc   : read_upf                                                                                    
#purpose: proc to read UPF and create UPF loader if needed 
#usage  : read_upf upf_path design des_type side 
################################################################################
proc read_upf { upf_path design des_type { side "" } } {
	######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "read_upf procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global env ivar ref impl 
    
    set task $ivar(task)

    iproc_msg -info "Reading $side side"
    if { $side eq "REF" } {
        set container "r"
        set ivar_side "golden"
		current_design $ref
    } else {
        set container "i"
        set ivar_side "revised"
		current_design $impl
    }

    if { $des_type eq "rtl" && [info exists ivar($task,gen_hier_upf_rtl)] && (!$ivar($task,gen_hier_upf_rtl)) } {
		if { ![load_upf -target $ivar($task,${ivar_side}_target) -$container $upf_path] } {
			iproc_msg -error "load_upf failed"
			exit -1
		} 
    } else {
        if { ![info exists ivar($design,child_modules)] || $ivar($design,child_modules) eq "" } {
            iproc_msg -info "No child modules found for $design"
			if { ![load_upf -target $ivar($task,${ivar_side}_target) -$container $upf_path] } {
				iproc_msg -error "load_upf failed"
				exit -1
			}
        } else {
			iproc_msg -info "Hierarchical Design , so creating Loader UPF for $design design @ $env(PWD)/outputs/${design}_${ivar_side}_upf_loader.tcl"

            set load_upf_file "$env(PWD)/outputs/${design}_${ivar_side}_upf_loader.tcl"
            if { [catch {set FH [open $load_upf_file "w"]} errMsg] } {
                iproc_msg -error "$errMsg"
                exit
            }
            
            if { [info exists ivar($task,child,${ivar_side}_upf_extn)] && $ivar($task,child,${ivar_side}_upf_extn) ne "" } {
                set upf_extn $ivar($task,child,${ivar_side}_upf_extn)
            } else {
                set upf_extn ".upf"
            }

            set depth_list ""
            array set string_array {}

			foreach child_mod $ivar($design,child_modules) {
				set mod_instance [get_attribute [get_cells -hierarchical * -filter "ref_name =~ $child_mod"] full_name]
				foreach child_instance $mod_instance {
					if { [regexp {.*:\/[A-Za-z0-9_]*\/[A-Za-z0-9_]*\/(.*)} $child_instance full instance_scope] } {
						set num_slashes [llength [regexp -all -inline / $instance_scope]]
                        set depth [expr { $num_slashes + 1 }]

                	    if { [info exists ivar($task,all,${ivar_side}_path)] && $ivar($task,all,${ivar_side}_path) ne "" } {
                	        set hier_upf $ivar($task,all,${ivar_side}_path)/${child_mod}${upf_extn}
                	    } elseif { [info exists ivar($task,$child_mod,${ivar_side}_path)] && $ivar($task,$child_mod,${ivar_side}_path) ne "" } {
                	        set hier_upf $ivar($task,$child_mod,${ivar_side}_path)/${child_mod}${upf_extn}
                	    } else {
                	        iproc_msg -error "UPF path for child $child_mod is not found"
                	        #exit -1
                	    }

                	    if { [file exists $hier_upf] } {
                	        lappend string_array($depth) "load_upf $hier_upf -scope $instance_scope"
                	    } elseif { [file exists ${hier_upf}.gz] } {
                	        lappend string_array($depth) "load_upf $hier_upf.gz -scope $instance_scope"
                	    } else {
                	        iproc_msg -error "Child level UPF file $hier_upf not found"
                	        return 
                	    }

                        if { [lsearch $depth_list $depth] < 0 } {
                            lappend depth_list $depth
                        }
					}
				}
			}

		    set sorted_depth [lsort -decreasing $depth_list]
            
            foreach counter $sorted_depth {
                foreach line $string_array($counter) {
                    puts $FH "$line"
                }
            }
		
			puts $FH "load_upf $upf_path"
            close $FH	

			iproc_msg -info "Reading $side Hierarchical upf $load_upf_file"
			if { ![load_upf -target $ivar($task,${ivar_side}_target) -$container $load_upf_file] } {	
				iproc_msg -error "load_upf failed"
				exit -1 
			}	
		}
	}
}
define_proc_attributes read_upf \
    -info "proc to read UPF and create UPF loader if needed"


################################################################################
#proc   : gen_sig_xml                                                                                    
#purpose: proc to generate sigtable xml used for scanBA 
#usage  : gen_sig_xml design 
################################################################################
proc gen_sig_xml { design } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "gen_sig_xml procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################

	global env ivar ref impl
	set task $ivar(task)

    if { [info exists ivar($task,gen_sig_table)] && (!$ivar($task,gen_sig_table)) } {
        iproc_msg -info "gen_sig_xml is disabled for this run"
        return 
    }
  
	if { [info exists ivar($task,r2r_register_mapping)] && [file exists $ivar($task,r2r_register_mapping)] } {
		set RTLMAP [open $ivar($task,r2r_register_mapping) r]
		iproc_msg -info "Using R2R register mapping file $ivar($task,r2r_register_mapping) to create sig table" 
	} else {
		iproc_msg -warning "No R2R register mapping file found to create sig table" 
		set RTLMAP ""
	}

	if { [file exists reports/$design.register_mapping.rpt] } {
		set GATEMAP [open reports/$design.register_mapping.rpt r] 
	} else {
		iproc_msg -error "R2G register mapping file not found,unable to generate sigtable"
		return
	}

	annotate_trace -stop

	set q {"}

	set OUTFILE [open reports/$design.sigtable.xml w]
	
	# array to store mapping between names in RTL-to-RTL verification
	# format is single list of impl name/polarities corresponding to ref name
	# 0          1            2
	# ref_object ref_polarity impl_polarity
	array set rtlobjects ""
	
	if { $RTLMAP != "" } {
		while { [gets $RTLMAP line] >= 0 } {
			switch -regexp $line {
				{^# (?:Registers|Blackbox Pins|Ports)} {
					# FM groups object types in the report with comment headers preceding each group
					regexp {^# ((?:Registers|Blackbox Pins|Ports))} $line full type
					continue
				}
				{^oref} {
					# FM write_register_mapping will output multiple oref lines for instantiated registers, one line per output, so skip consecutive oref lines
					# ...should not happen in RTL-to-RTL run
					if { $state == "in_map" } {
						iproc_msg -warning "Ignoring multiple ref object in RTL map file: $line"
						continue
					} else {
						set state in_map
						regexp {^oref ((?:pos|neg)) (\S+)} $line full ref_polarity ref_object
						continue
					}
				}
				{^impl} {
					regexp {^impl ((?:pos|neg)) (\S+)} $line full impl_polarity impl_object
					# get rid of backslashes in object names like path/to/somehier\[field\]/a_reg that show up on the impl side in the RTL-to-RTL verify for some reason
					set impl_object [regsub -all {\\} $impl_object ""]
					if { $type == "Blackbox Pins" } {
						# skip *unread* blackbox pins
						if { [regexp {.*\*unread\*/IN$} $ref_object] } {
							continue
						}
						# map file has black-box pins but sigtable should only have black-boxes
						if { ![info exists objects([file dirname $ref_object])] } {
							set ref_object [file dirname $ref_object]
							set impl_object [file dirname $impl_object]
						} else {
							continue
						}
					}
					set rtlobjects($impl_object) [list $ref_object $ref_polarity $impl_polarity]
					continue
				}
				{^$} {
					# empty lines delineate match groups, so reset state when encountering empty line
					set state ""
					continue
				}
			}
		}
	close $RTLMAP
	}

	# array to store original ref object and all impl mappings
	# format is list-of-lists for each impl mapping
	# 0           1        2         3             4              5            6             7            8
	# impl_object ref_type impl_type ref_direction impl_direction ref_polarity impl_polarity multiple_ref found_in_rtlmap
	array set objects ""
	
	# array to store multiple ref objects that correspond to original ref object
	# format is list-of-lists for eaach additional ref object
	# 0                     1                       2
	# additional_ref_object additional_ref_polarity additional_ref_object_found_in_rtlmap
	array set multiple_ref_objects ""
	
	set multiple_ref 0

	while { [gets $GATEMAP line] >= 0 } {
		switch -regexp $line {
			{^# (?:Registers|Blackbox Pins|Ports)} {
				# FM groups object types in the report with comment headers preceding each group
				# $prefix is used to avoid prefixing ports with /
				regexp {^# ((?:Registers|Blackbox Pins|Ports))} $line full type
				if { $type == "Ports" } {
					set ref_type "node"
					set impl_type "node"
					set prefix ""
				} elseif { $type == "Registers" } {
					set ref_type "state"
					set impl_type "state"
					set prefix "/"
				} elseif { $type == "Blackbox Pins" } {
					set ref_type "bbox"
					set impl_type "bbox"
					set prefix "/"
				}
				continue
			}
			{^oref} {
				# handle multiple ref objects (either due to instantiated registers or reg_merging)
				# only registers will have multiple ref objects so no need to worry about port/bbpin issues
				if { $state == "in_map" } {
					regexp {^oref ((?:pos|neg)) (\S+)} $line full additional_ref_polarity additional_ref_object
					if { [info exists rtlobjects($additional_ref_object)] } {
						set additional_ref_object_found_in_rtlmap 1
						set additional_ref_object [lindex $rtlobjects($additional_ref_object) 0]
					} else {
						set additional_ref_object_found_in_rtlmap 0
						#iproc_msg -warning "$additional_ref_object not found in RTL-to-RTL mapping"
					}
					# instantiated registers have pin-based entries that all correspond to a single non-instantiated register in the RTL-to-RTL map -- avoid generating duplicate entries
					if { $additional_ref_object == $ref_object } {
						continue
					} else {
						set multiple_ref 1
						lappend multiple_ref_objects($prefix$ref_object) [list $prefix$additional_ref_object $additional_ref_polarity $additional_ref_object_found_in_rtlmap]
						continue
					}
				} else {
					# this is the first ref object for a given map group
					set state in_map
					regexp {^oref ((?:pos|neg)) (\S+)} $line full ref_polarity ref_object
					if { $type == "Ports" } {
						set ref_direction [get_attribute [get_ports -quiet $ref/$ref_object] direction]
						# change "in"/"out" to "input"/"output"
						if { $ref_direction != "inout" } { set ref_direction ${ref_direction}put }
					} else {
						set ref_direction "internal"
					}
					if { [info exists rtlobjects($ref_object)] } {
						set ref_object_found_in_rtlmap 1
						set ref_object [lindex $rtlobjects($ref_object) 0]
					} else {
						set ref_object_found_in_rtlmap 0
						#iproc_msg -warning "$type $ref_object not found in RTL-to-RTL mapping"
					}
					continue
				}
			}
			{^impl ((?:pos|neg)) (\S+)} {
				regexp {^impl ((?:pos|neg)) (\S+)} $line full impl_polarity impl_object
				if { $impl_polarity == "pos" } {
					set negate 0
				} elseif { $impl_polarity == "neg" } {
					set negate 1
				}
				if { $type == "Ports" } {
					set impl_direction [get_attribute [get_ports $impl/$impl_object] direction]
					if { $impl_direction != "inout" } { set impl_direction ${impl_direction}put }
				} else {
					set impl_direction "internal"
				}
				if { $type == "Blackbox Pins" } {
					# skip *unread* and fm_hft_bb blackbox pins
					if { ([regexp {.*\*unread\*/IN$} $ref_object]) || ([regexp {.*/fm_hft_bb/.*#} $ref_object]) } {
						continue
					}
					# map file has black-box pins but sigtable should only have black-boxes
					if { ![info exists objects($prefix[file dirname $ref_object])] } {
						set ref_object [file dirname $ref_object]
						set impl_object [file dirname $impl_object]
					} else {
						continue
					}
				}
				lappend objects($prefix$ref_object) [list $prefix$impl_object $ref_type $impl_type $ref_direction $impl_direction $ref_polarity $impl_polarity $multiple_ref $ref_object_found_in_rtlmap]
				continue
			}
			{^impl c=} {
				regexp {^impl c=([01])} $line full impl_object
				lappend objects($prefix$ref_object) [list $impl_object const const internal internal pos pos 0 $ref_object_found_in_rtlmap]
				continue
			}
			{^$} {
				# empty lines delineate match groups, so reset state when encountering empty line
				set multiple_ref 0
				set state ""
				continue
			}
		}
	}
  
	close $GATEMAP
	
	redirect -variable constant_report {report_constants}
	
	# variable to store constant info
	# 0           1      2        3         4             5              6
	# impl_object negate ref_type impl_type ref_direction impl_direction ref_object
	set constants ""
	
	foreach line [split $constant_report \n] {
		switch -regexp -- $line {
			{^ +([01]) +([a-z]+) +([a-zA-Z0-9]+:.*$)} {
				regexp -- {^ +([01]) +([a-z]+) +([a-zA-Z0-9]+:.*$)} $line full value type objectID
				if { [string match $ref* $objectID] } {
					set ref_object [regsub $ref $objectID ""]
					set impl_object $value
				} elseif { [string match $impl* $objectID] } {
					set ref_object $value
					set impl_object [regsub $impl $objectID ""]
				}
				if { $type=="cell" } {
					set ref_direction "internal"
					set impl_direction "internal"
				} else {
					set ref_direction "input"
					set impl_direction "input"
				}
				lappend constants [list $impl_object 0 const const $ref_direction $impl_direction $ref_object 1]
			}
		}
	}
	
	puts $OUTFILE {<?xml version="1.0" ?>}
	puts $OUTFILE "<!--"
	puts $OUTFILE "//========================================================"
	puts $OUTFILE "//File Name : $design.sigtable.xml"
	puts $OUTFILE "//Note   : This file is manually generated using a script"
	puts $OUTFILE "//Tool   : FORMALITY"
	puts $OUTFILE "//========================================================"
	puts $OUTFILE "-->"
	puts $OUTFILE "<SIGTABLE>"
	puts $OUTFILE "  <BLOCK NAME=$q$design$q>"

	foreach object [lsort [array names objects]] {
		# iterate over all impl objects in this map group
		foreach impl_object $objects($object) {
			# skip black-box objects that weren't found in RTL-to-RTL run to avoid outputting lines for synthesis-CTECH blackboxes
			if { ![lindex $impl_object 8] && ( [lindex $impl_object 1] == "bbox" ) } {
				continue
			}
			# compare ref polarity to impl polarity: if same then negate is 0
			if { [lindex $impl_object 5] == [lindex $impl_object 6] } {
				set negate 0
			} else {
				set negate 1
			}
            # if ref object is a port ("node" type) and direction is "put" then FM failed to find the port due to SVF changes, so use impl port direction instead
            if { [lindex $impl_object 1] == "node" && [lindex $impl_object 3] == "put" } {
                    set impl_object [lreplace $impl_object 3 3 [lindex $impl_object 4]]
            }
			puts $OUTFILE "    <MAP RTL_SIG=$q$object$q SCH_SIG=$q[lindex $impl_object 0]$q NEGATE=$q$negate$q RTL_TYPE=$q[lindex $impl_object 1]$q SCH_TYPE=$q[lindex $impl_object 2]$q RTL_DIRECTION=$q[lindex $impl_object 3]$q SCH_DIRECTION=$q[lindex $impl_object 4]$q />"
			puts $OUTFILE ""
			# if there are multiple ref objects, then iterate on them too and provide mapping for each multiple ref object to each impl object
			if { [lindex $impl_object 7] } {
				foreach multiple_ref_object $multiple_ref_objects($object) {
				# compare ref polarity to impl polarity: if same then negate is 0
				if { [lindex $multiple_ref_object 1] == [lindex $impl_object 6] } {
					set negate 0
				} else {
					set negate 1
				}
                # if multiple ref object is a port ("node" type) and direction is "put" then FM failed to find the port due to SVF changes, so use impl port direction instead
                if { [lindex $multiple_ref_object 1] == "node" && [lindex $multiple_ref_object 3] == "put" } {
                        set multiple_ref_object [lreplace $multiple_ref_object 3 3 [lindex $multiple_ref_object 4]]
                }
				puts $OUTFILE "    <MAP RTL_SIG=$q[lindex $multiple_ref_object 0]$q SCH_SIG=$q[lindex $impl_object 0]$q NEGATE=$q$negate$q RTL_TYPE=$q[lindex $impl_object 1]$q SCH_TYPE=$q[lindex $impl_object 2]$q RTL_DIRECTION=$q[lindex $impl_object 3]$q SCH_DIRECTION=$q[lindex $impl_object 4]$q />"
				puts $OUTFILE ""
				}
			}
		}
	}

	foreach constant $constants { 
		puts $OUTFILE "    <MAP RTL_SIG=$q[lindex $constant 6]$q SCH_SIG=$q[lindex $constant 0]$q NEGATE=$q[lindex $constant 1]$q RTL_TYPE=$q[lindex $constant 2]$q SCH_TYPE=$q[lindex $constant 3]$q RTL_DIRECTION=$q[lindex $constant 4]$q SCH_DIRECTION=$q[lindex $constant 5]$q />"
		puts $OUTFILE ""
	}
	
	puts $OUTFILE "  </BLOCK>"
	puts $OUTFILE "</SIGTABLE>"
	
	close $OUTFILE
    iproc_msg -info "Stage_for_runtime_aggregation gen_sig_xml"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"

	annotate_trace -start

}
define_proc_attributes gen_sig_xml \
    -info "proc used to generate sigtable for scanBA"


################################################################################
#proc	    : report_ivar_change 											
#purpose    : To track and generate ivar changes throught the fev template's runtime  
#usage	    : report_ivar_change 
################################################################################
proc report_ivar_change { design } {
    #HSD 14020319040
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "report_ivar_change procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    global ivar env 
    set rpt_file ./reports/$design.ivar_history.rpt
    iproc_msg -info "Creating ivar history info @ ./reports/$design.ivar_history.rpt"
    set var_rpt_fp [open $rpt_file w]
    set ivar_entries [lsort -unique -increasing -ascii  [array names ivar]]
    iproc_msg -info "Total Ivar entries found : [llength $ivar_entries]"
    puts $var_rpt_fp "## Total IVAR entries : [llength $ivar_entries]"
    puts $var_rpt_fp "#FORMAT: SET IVAR(ENTRY) VALUE ; # most recent place......initial place) -> paths are reversed.  "

    foreach entry $ivar_entries {
        set tmp_ivar_source ""
        set tmp_ivar_source [find_ivar_source $entry]
        if { $ivar($entry) eq "" } {
            puts $var_rpt_fp "set ivar($entry) \"\" ; # $tmp_ivar_source"
        } else {
            puts $var_rpt_fp "set ivar($entry) [list $ivar($entry)] ; # $tmp_ivar_source"
        }
    }    
    close $var_rpt_fp
    iproc_msg -info "Stage_for_runtime_aggregation report_ivar_change"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"

}
define_proc_attributes report_ivar_change \
   -info "To track and generate ivar changes throught the fev template's runtime"


################################################################################
#proc	    : find_ivar_source 											
#purpose    : Helper proc for report_ivar_change proc  
#usage	    : find_ivar_source 
################################################################################
proc find_ivar_source { index } {
    set item ""
    set var_name ::ivar($index)
    if { [info exists ::variable_logger::_history_arr($var_name)] } {
        #set item [ lindex [split [lindex $::variable_logger::_history_arr($var_name) end] " "] end-2 ]
        set var_data $::variable_logger::_history_arr($var_name)
        foreach data $var_data {
            lappend item [lindex [split $data " "] end-2]  
        }
        set item [lreverse $item] 
    } else {
        set item "No information about $var_name was found"
    }
    return $item
}
define_proc_attributes find_ivar_source \
   -info "Helper proc for report_ivar_change proc "

################################################################################
#proc	    : add_blackbox_hips 											
#purpose    : To put black box attribute on all HIPs  
#usage	    : add_blackbox_hips
#################################################################################
proc add_blackbox_hips {} {
	######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    puts "INTEL_INFO: add_blackbox_hips procedure is invoked from file: [lindex [info frame 6] 5]"
    ##################################################################################
    global ivar env ref impl
    set task $ivar(task)
    
    if { [info exists ivar($task,blackbox_hips)] && (!$ivar($task,blackbox_hips)) } {
        iproc_msg -info "add_blackbox_hips is disabled for this run"
        return
    }

	iproc_msg -info "Black boxing HIPs"

	annotate_trace -stop

	current_design $ref
	current_container r
	set ref_bboxes ""
	set ref_bboxes [get_attribute [get_cells -hierarchical * -filter "is_macro_cell == true"] full_name]
	foreach bbox $ref_bboxes {
		set_black_box $bbox
	}

	current_design $impl
	current_container i
	set impl_bboxes ""
	set impl_bboxes [get_attribute [get_cells -hierarchical * -filter "is_macro_cell == true"] full_name]
	foreach bbox $impl_bboxes {
		set_black_box $bbox
	}
	iproc_msg -info "Stage_for_runtime_aggregation add_blackbox_hips"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"
	annotate_trace -start

}
define_proc_attributes add_blackbox_hips \
   -info "To Black box HIPs"


####################################################################################
#proc	: report_bboxes_parametrization											
#purpose: Proc to generate reports needed for CheckforParameterizedBBoxes Audit check 
#usage	: report_bboxes_parametrization { fev_type design }
####################################################################################
proc report_bboxes_parametrization { fev_type design } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "report_bboxes_parametrization procedure is invoked from file: [lindex [info frame 6] 5]"
    ##################################################################################
    global env ivar
    set task $ivar(task)
    
    if { $fev_type eq "g2g" || $fev_type eq "eco" } {
        iproc_msg -info "Fev Type not supported, skipping bboxes_parametrization_info report generation."
        return
    }
        
    annotate_trace -stop

    set bb_data ""
     
    if { $fev_type eq "r2r" || $fev_type eq "fev_fm_lite" } {
        redirect -variable bb_data "report_black_boxes"
    }

    #array set side_map "G golden R revised"
    if { $fev_type eq "r2g" } {
        redirect -variable bb_data "report_black_boxes -r"
        
    }

    set lines [split $bb_data "\n"]

    set report_file "reports/${design}.bboxes_parametrization_info.rpt"
    set FH [open $report_file w ]
    puts $FH "#Container,Module,Instance,Parameter,Value"


    foreach line $lines {
        #puts "KB line: $line"
        if { [regexp {^\s+([ri]:\/\S+)} $line match inst_name] } {
            if { [regexp {Reference      :} $line] } { continue }
            if { [regexp {Implementation :} $line] } { continue }
            set instance [get_attribute [get_cells $inst_name] full_name]
            #puts "isntance: $instance"
            set module [get_attribute [get_cells $instance] ref_name]
            #puts "module: $module"
            set container [get_attribute [get_cells $instance] container_name]
            #puts "container: $container"
            set parameters [get_attribute [get_cells $instance] hdl_parameters]
            #puts "parameters: $parameters"
            if { [info exists parameters]  && $parameters != "" } {
                #puts "parameters: $parameters"
                foreach { all param val } [regexp -all -inline {(\S+)=([^\"\s]+|\"[^\"]+\")} $parameters] {
                    regsub  -all {\,$} $val "" val
                    set module_hash_rem [lindex [split $module "#"] 0]
                    puts $FH "$container,$module_hash_rem,$instance,$param,$val"
                }
            }
        }
    }

             
    close $FH
    iproc_msg -info "Done writing report: $report_file"
    annotate_trace -start
}

define_proc_attributes report_bboxes_parametrization \
    -info "Proc to generate reports needed for CheckforParameterizedBBoxes Audit check"


####################################################################################
#proc	: report_unmatched_bboxes											
#purpose: Proc to generate custom report needed for NonMatchingBBoxes Audit check 
#usage	: report_unmatched_bboxes { design }
####################################################################################
proc report_unmatched_bboxes { design } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "report_unmatched_bboxes procedure is invoked from file: [lindex [info frame 6] 5]"
    ##################################################################################
    annotate_trace -stop

    set side_cont "ref impl"

    # report file used for nonmatchingbbox audit
    set report_file_1 "reports/${design}.black_boxes_unmatched.rpt"
    set FH [open $report_file_1 w ]
    puts $FH "**************************************************"
    puts $FH "Report        : unmatched blackboxes"
    puts $FH "Note          : For detailed instance report look into black_boxes.rpt"
    puts $FH "**************************************************"

    # report file to map unmatched bbox instances to their respective modules
    set report_file_2 "reports/${design}.black_boxes_unmatched_binding.rpt"
    set rH [open $report_file_2 w ]
    puts $rH "**************************************************"
    puts $rH "Report        : unmatched blackboxes binding"
    puts $rH "Note          : This report will have the list of unmatched blackboxes and their respective modules"
    puts $rH "**************************************************"

    foreach side $side_cont {
        puts $FH "\nContainer: $side\n"
        puts $rH "\nContainer: $side"
        puts $rH "\tModule_name: Istance_name\n"

        # get all unmatched bbox points
        set unmatched_bbox_points [report_unmatched_points -list -point_type bbox -${side}]

        set unmatched_inst_bbox [dict create]

        # Performance optimization: Process all points at once instead of individually
        set total_points [llength $unmatched_bbox_points]
        
        if { $total_points > 0 } {
            # Get all cells at once to avoid repeated individual queries
            set all_cells [get_cells $unmatched_bbox_points]

            # Get all mod_names at once - much faster than individual queries
            set all_mod_names [get_attribute $all_cells ref_name]
            
            # Process the lists together
            for {set i 0} {$i < $total_points} {incr i} {
                set inst_name [lindex $unmatched_bbox_points $i]
                set mod_name [lindex $all_mod_names $i]
                
                # modulenames will have 'ffff#PWR_BBOX_jj'
                # now remove anything after #, split by # and preserve the first element.
                set mod_name [lindex [split $mod_name "#"] 0]

                if { [dict exists $unmatched_inst_bbox $mod_name] } {
                    dict lappend unmatched_inst_bbox $mod_name $inst_name
                } else {
                    dict set unmatched_inst_bbox $mod_name [list $inst_name]
                }
            }
        }

        # Writing into report FH
        iproc_msg -info "Unmatched Black_box found on ${side} side: [llength [dict keys $unmatched_inst_bbox]]"
        dict for {mod count} $unmatched_inst_bbox {
            puts $FH "\t$mod"
        }

        # Writing into report rH
        dict for {key value} $unmatched_inst_bbox {
            foreach item $value {
                puts $rH "\t$key : $item"
            }
        }
    }

    close $FH
    close $rH
    iproc_msg -info "Done writing report: $report_file_1"
    iproc_msg -info "Done writing report: $report_file_2"
    annotate_trace -start
}

define_proc_attributes report_unmatched_bboxes \
    -info "Proc to generate custom report needed for NonMatchingBBoxes Audit check"

################################################################################
#proc	    : report_supply_check_results											
#purpose    : Reports to be dumped out after supply connection checks happen 
#usage	    : report_supply_check_results <DESIGN NAME>
################################################################################
proc report_supply_check_results { design } {
    ######COPY THIS LINE WHEN YOU OVERRIDE THIS PROCEDURE ###########################
    iproc_msg -info "report_supply_check_results procedure is invoked from file: [lindex [info frame 6] 5]"
    #################################################################################
    
    global ivar env

    report_supply_connection_checks -summary > reports/$design.report_supply_connection_checks.rpt
    report_supply_connection_checks -status unmatched -cell_type macro > reports/$design.report_supply_connection_checks_unmatched_macro.rpt
    report_supply_connection_checks -status unmatched -cell_type reg > reports/$design.report_supply_connection_checks_unmatched_reg.rpt
    report_supply_connection_checks -status matched -cell_type macro > reports/$design.report_supply_connection_checks_matched_macro.rpt
    report_supply_connection_checks -status matched -cell_type reg > reports/$design.report_supply_connection_checks_matched_reg.rpt
    report_supply_connection_checks -status all -cell_type macro > reports/$design.report_supply_connection_checks_all_macro.rpt
    report_supply_connection_checks -status all -cell_type reg > reports/$design.report_supply_connection_checks_all_reg.rpt
    report_supply_connection_checks -status failed > reports/$design.report_supply_connection_checks_failed.rpt
    report_supply_connection_checks -status unmatched -exclude *pwc_clk_gate* > reports/$design.report_supply_connection_checks_unmatched.rpt

    
}
define_proc_attributes report_supply_check_results \
    -info "Reports for supply connection check results "


##TEMPLATE FOR NEW PROCS
################################################################################
#proc	    : PROC NAME											
#purpose    : DEFINE PURPOSE OF PROC  
#usage	    : EXAMPLE OF HOW TO USE IT
################################################################################
# PROC XYZ {}{
#    
#}
#define_proc_attributes PROC NAME(XYZ) \
#  -info "QUICK DEFINITIONOF XYZ PROC "


