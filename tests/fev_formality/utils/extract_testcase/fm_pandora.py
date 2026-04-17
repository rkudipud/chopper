#/usr/intel/bin/python3.11.1
####################################################################################################
####################################################################################################
#
#                                                                     
#
#
####################################################################################################


from __future__ import print_function
import hashlib
import shutil
import signal
import re
import tracemalloc
import os
from timeit import default_timer as timer
import itertools
import threading
import time
import sys



class GracefulExiter():

    def __init__(self):
        self.state = False
        signal.signal(signal.SIGINT, self.change_state)

    def change_state(self, signum, frame):
        print(f"{bcolors.WARNING}ctrl+c Received, press again to exit{bcolors.ENDC}", flush=True)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        self.state = True

    def exit(self):
        return self.state



errorVar = False
done = False

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'



#compiled regex
script_path_regex = re.compile (r"Script:\s*(.*)/runs/(.*)",flags=re.I)



#here is the animation
def animate():
    width = os.get_terminal_size().columns
    for c in itertools.cycle(["|","/","-","\\","|","/","-","\\"]):
        if done:
            break
        print(f"Processing Log....... {c}", flush = True, end="\r")
        time.sleep(0.1)





def checksum (file1,file2) :
    with open(file1, 'rb') as file_to_check1:
        data_1= file_to_check1.read()    
        hash_1 = hashlib.md5(data_1).hexdigest()
        #print(f"Hash of {file1} is : {hash_1} (md5)")
    with open(file2, 'rb') as file_to_check2:
        data_2 = file_to_check2.read()    
        hash_2 = hashlib.md5(data_2).hexdigest()
        #print(f"Hash of {file2} is : {hash_2} (md5)")
    if hash_1 == hash_2:
        return True
    else:
        return False

def id_creator(dest_path,block_name,tech,task,reference_folder,implementation_folder):
#creates idcard for the source folder
    id_file_path = os.path.join(dest_path,block_name,"id.csh")
    if (os.path.exists(id_file_path)):
        with open(id_file_path, 'r') as file:
            content = file.readlines()
        for line in content:    
            if 'fub_collaterals' in line:
                #print(f'Fub Collaterals already exists with : {content.index(line)}', flush=True)
                matches = re.search(r"\(.*\)", line, re.IGNORECASE | re.VERBOSE)
                if (reference_folder not in matches.group() ):
                    #print (f"not, {content[content.index(line)]}", flush=True)
                    content[content.index(line)] = content[content.index(line)].replace(")",f"{reference_folder} )")
                if (implementation_folder not in matches.group() ):
                    #print (f"not, {content[content.index(line)]}", flush=True)
                    content[content.index(line)] = content[content.index(line)].replace(")",f"{implementation_folder} )")
            if 'fub_tasks' in line:
                #print(f'Fub Tasks already exists with : {content.index(line)}', flush=True)
                matches = re.search(r"\(.*\)", line, re.IGNORECASE | re.VERBOSE)
                if (task not in matches.group() ):
                    #print (f"not, {content[content.index(line)]}", flush=True)
                    content[content.index(line)] = content[content.index(line)].replace(")",f"{task} )")
        #print(content)  
        with open(id_file_path, 'w') as file:
            file.writelines( content ) 
    else:
        l=f"#!/bin/csh -f\n\
set fub_name={block_name}\n\
set fub_collaterals = \"( {reference_folder} {implementation_folder} )\"\n\
set fub_tasks = \"( {task} )\"\n\
set fub_techs = \"( {tech} )\"\n\
#nb_mode:64G_4C\n\n\
    "
        with open(id_file_path, 'w') as file:
            file.writelines( l )
    print (f"{bcolors.OKCYAN}---> ID file Created{bcolors.ENDC}", flush=True)



def vars_creator(dest_path,block_name):
    vars_file_path = os.path.join(dest_path,block_name,"scripts","vars.tcl")
#needs to be updaeted
    l = '\n\
set ivar(link_libs) ""    \n\
set libs_copied [glob -nocomplain -path $env(ward)/runs/$env(block)/$env(tech)/$env(flow)/$env(task)/src_backup/library/db/ * ] \n\
set all_libs "" \n\
foreach individual_path $libs_copied { \n\
    regexp {([^\/]+$)} $individual_path libname 	\n\
    lappend all_libs $libname \n\
}\n\n\
set ivar(link_libs) $all_libs \n\
foreach linkLib $ivar(link_libs) {  \n\
    set ivar(lib,$linkLib,use_ccs) 0 \n\
    set ivar(lib,$linkLib,db_nldm_filelist,TT_100) [glob -nocomplain -path $env(ward)/runs/$env(block)/$env(tech)/$env(flow)/$env(task)/src_backup/library/db/ *$linkLib* ] \n\
} \n\n'


    if(os.path.exists (vars_file_path)):
        shutil.copyfile(vars_file_path, os.path.join(dest_path,block_name,"scripts","vars.tcl_orig"))
    with open (vars_file_path,"a+") as vars:
        vars.write("\n")
        vars.write(l)
        print (f"{bcolors.OKCYAN}---> Modified Vars{bcolors.ENDC}", flush=True)
    return

def rtl_list_path_modifier(dest_path,block_name,name,path):
    if( os.path.exists ( os.path.join(path,name)) ):
        shutil.copyfile( os.path.join(path,name), os.path.join(path,f"{name}_orig") )
    os.system(f"sed -i '/lappend/ s/\"//g' {os.path.join(path,name)}")
    os.system(f"sed -i 's#/nfs/#\$env(ward)/runs/$env(block)/$env(tech)/$env(flow)/$env(task)/src_backup/rtl/nfs/#g' {os.path.join(path,name)}")
    os.system(f"sed -i 's#/p/#\$env(ward)/runs/$env(block)/$env(tech)/$env(flow)/$env(task)/src_backup/rtl/p/#g' {os.path.join(path,name)}")
    if ("sim" in name):
        shutil.copyfile(os.path.join(path,name), os.path.join(dest_path,block_name,"scripts","rtl_2stage_sim_new.tcl"))
    else:
        shutil.copyfile(os.path.join(path,name), os.path.join(dest_path,block_name,"scripts","rtl_2stage_new.tcl"))
    print (f"{bcolors.OKCYAN}--> Modified {name} to new paths{bcolors.ENDC}",flush = True)
    return



def main(argv):
    t = threading.Thread(target=animate)
    t.start()
    global done
    global errorVar
    tracemalloc.start()
    #######################################################################################################################
    #parsing input
    reference_folder = "fe_collateral"
    implemented_folder = "finish"
    try:
        if( len(argv) != 5 ):
            print (f"{bcolors.FAIL}Error:{bcolors.ENDC} Not Enough Arguments.\nTry:\npython {argv[0]} <log's realpath> <destination> <Reference_folder_name> <Implemented_folder_name>", flush=True)
            sys.exit(1)
        log_path  = (argv)[1]
        dest_path = (argv)[2]
        reference_folder = (argv)[3]
        implemented_folder = (argv)[4]
        print (f"{bcolors.OKCYAN}Given log Path:{bcolors.ENDC} {log_path}", flush=True)
        print (f"{bcolors.OKCYAN}Given Destination Path:{bcolors.ENDC} {dest_path}\n", flush=True)
        #print (f"Reading log File", flush=True)
    except IndexError as e:
        print(f"{bcolors.FAIL}Exception Encountered:{bcolors.ENDC} {e}", flush=True)
        print (f"{bcolors.FAIL}Error:{bcolors.ENDC} Check your argumemts.\nTry: \npython {argv[0]}  <log's realpath> <destination> <Reference_folder_name> <Implemented_folder_name>", flush=True)
        errorVar = True
        sys.exit(1)


    start = timer()

    ##stats
    #global varibales
    block_name=""
    tech=""
    flow=""
    task=""
    log_name=""
   

    #predefined variables
    #initial states
    ref = False;impl = False;rtl_mode =False;gate_mode = False;design=False;upf = False;td_files = False; child = False

    #stats
    count =0
    rtl_files = 0
    design_files = 0
    db_files =0
    upf_files =0
    

    #######################################################################################################################
    try:
        
        with open(log_path, 'r') as source_log:
            for Line in source_log:
                count += 1
                #print(Line.strip())
                line = Line.strip()
                #regex to match the  Script line 
                if script_path_regex.match(line):
                    ward=script_path_regex.match(line).group(1)
                    data_path = script_path_regex.match(line).group(2)
                    data_path = data_path.split('/')
                    block_name=data_path[0]
                    tech=data_path[1]
                    flow=data_path[2]
                    task=data_path[3]
                    log_name=log_path.rsplit('/',1)[-1]

                    print ( f"{bcolors.OKBLUE}Ward Path:{bcolors.ENDC} {ward}" , flush=True)
                    print ( f"{bcolors.OKBLUE}Block_Name:{bcolors.ENDC} {block_name}" , flush=True)
                    print ( f"{bcolors.OKBLUE}Block_Tech:{bcolors.ENDC} {tech}" , flush=True)
                    print ( f"{bcolors.OKBLUE}Block_Flow:{bcolors.ENDC} {flow}" , flush=True)
                    print ( f"{bcolors.OKBLUE}Block_Task:{bcolors.ENDC} {task}" , flush=True)
                    print ( f"{bcolors.OKBLUE}Block_Log name:{bcolors.ENDC} {log_name}\n" , flush=True)

                    try:
                        print (f"{bcolors.BOLD}Creating Extracted Dirs{bcolors.ENDC}", flush=True)
                        if (os.path.exists(dest_path)) :
                            os.makedirs(os.path.join(dest_path,block_name),exist_ok = True,mode=0o777)
                            os.makedirs(os.path.join(dest_path,block_name,"scripts"),exist_ok = True,mode=0o777)
                            os.makedirs(os.path.join(dest_path,block_name,"scripts",task),exist_ok = True,mode=0o777)
                            if os.path.exists (os.path.join(dest_path,block_name,task+".orig.log")) :
                                if checksum (os.path.join(dest_path,block_name,task+".orig.log"), log_path ):
                                    print (f"{bcolors.WARNING}-->same log file present in Testcase{bcolors.ENDC}\n", flush=True)      
                            else:
                                shutil.copyfile(log_path, os.path.join(dest_path,block_name,task+".orig.log"))
                    except OSError as error:
                        print (f"{bcolors.WARNING}Error in creating directory :{bcolors.ENDC}\n" + str(error), flush=True)
                        errorVar = True
                        sys.exit(1)

                #end of if block
                #folder discovery


                
                #looks for SVF file and copies it.
                svf_file = re.match(r"\s*SVF\s*set\s*to\s*'(.*)'\s*",line,re.I)
                if(svf_file):
                    if (not os.path.exists(os.path.join(dest_path,block_name,implemented_folder))) :
                        os.makedirs(os.path.join(dest_path,block_name,implemented_folder),exist_ok = True,mode=0o777)
                    shutil.copyfile(svf_file.groups()[0].split(" ")[0], os.path.join(dest_path,block_name,implemented_folder,os.path.basename(svf_file.groups()[0].split(" ")[0])),follow_symlinks=True)
                    print(f"{bcolors.OKGREEN}copied{bcolors.ENDC} {svf_file.groups()[0].split('/')[-1]}", flush=True)

                #captures "loading db file"
                db_file = re.match(r"\s*loading\s*db\s*file\s*'(.*)'",line,re.I)
                if(db_file and not 'gtech.db' in db_file.groups()[0]):
                    try:
                        db_path = os.path.join(dest_path,block_name,"src_backup","library","db")
                        if (not os.path.exists(db_path)) :
                            os.makedirs(db_path,exist_ok = True,mode=0o777)
                        shutil.copyfile(db_file.groups()[0].strip(), os.path.join(db_path,os.path.basename(db_file.groups()[0].strip())),follow_symlinks=True)
                        #print (f"copied db file: {db_file.groups()[0].rsplit('/',1)[-1]}")
                        db_files +=1
                    except Exception as err:
                        print(f"{bcolors.FAIL}Exception Encountered:{bcolors.ENDC} {err}", flush=True)
                        errorVar = True
                        pass
                



                #Captures reference design
                side = re.match(r"\s*INFO:\s*Reading\s*(Reference|impleme.*)\s*(Design|upf)",line,re.I)
                if (side and re.search('refer',line, re.IGNORECASE)):
                    ref = True;impl=False
                if (side and re.search('implem',line, re.IGNORECASE)):
                    ref = False;impl=True
                if (side and re.search('design',line, re.IGNORECASE)):
                    design = True; upf = False
                if (side and re.search('upf',line, re.IGNORECASE)):
                    upf = True; design =False
                

                if(re.search(r"\s*INTEL_INFO\s*:\s*read_rtl\s*",line,re.I)):
                    rtl_mode =True; gate_mode = False

                if(re.search(r"\s*INTEL_INFO\s*:\s*read_gate\s*",line,re.I)):
                    rtl_mode =False; gate_mode = True

				#experimental - no actual function no logic
                if( (re.search(r"\s*file list\s*:\s*",line,re.I)) and re.search (r"rtl_list_2stage_sim.tcl",line,re.I)):
                    print(f"Experimental: {bcolors.UNDERLINE}rtl_list_2stage for sim exists{bcolors.ENDC}", flush=True)

                if( (re.search(r"\s*file list\s*:\s*",line,re.I)) and re.search (r"rtl_list_2stage.tcl",line,re.I)):
                    print(f"Experimental: {bcolors.UNDERLINE}rtl_list_2stage file (rtl) exists{bcolors.ENDC}", flush=True)

                if( (re.search(r"\s*creating Loader UPF\s*",line,re.I)) ):
                    print(f"{bcolors.WARNING} IT has Hier UPF be careful and scrutunise all the UPF files{bcolors.ENDC}", flush=True)


                # copy design verilog files for designs - the loaded design files
                design_file = re.search(r"\s*loading\s*(verilog|include|upf|design ware)\s*.*file\s*'(.*)'\s*",line,re.I)
                if(design_file and (design or upf)):
                    design_file = design_file.groups()[1].strip()
                    #decide on impl or ref
                    if (not ref and impl):
                        side_dir = os.path.join(dest_path,block_name,implemented_folder)
                    if (ref and not impl):
                        side_dir = os.path.join(dest_path,block_name,reference_folder)
                    if (not os.path.exists(side_dir)) :
                        os.makedirs(side_dir,exist_ok = True,mode=0o777)

                    #copy upf files
                    if( upf ):
                        shutil.copyfile(design_file, os.path.join(side_dir,os.path.basename(design_file)),follow_symlinks=True)
                        print(f"{bcolors.OKGREEN}copied{bcolors.ENDC} {design_file.split('/')[-1]}", flush=True)
                        upf_files +=1

                    #for gate mode ref and impl design file copy
                    if(gate_mode and not rtl_mode and not upf):
                        if (not ref and impl):
                            sub_break = design_file.split(implemented_folder)
                            #print(sub_break)
                        if (ref and not impl):
                            sub_break = design_file.split(reference_folder)
                            #print(sub_break)
                        copy_dir = os.path.join(side_dir,sub_break[-1].rsplit('/',1)[0].split("/",1)[-1])
                        os.makedirs(copy_dir,exist_ok = True,mode=0o777)
                        shutil.copyfile(design_file, os.path.join(copy_dir,os.path.basename(design_file)),follow_symlinks=True)
                        print(f"{bcolors.OKGREEN}copied{bcolors.ENDC} {design_file.split('/')[-1]}", flush=True)
                        design_files +=1

                    #rtl mode to copy files listed in rtllist file
                    if(rtl_mode and not gate_mode and not upf):
                        #creating src_backup/rtl
                        tc_rtl_path = os.path.join(dest_path,block_name,"src_backup","rtl")
                        if (not os.path.exists(tc_rtl_path)) :
                            os.makedirs(tc_rtl_path,exist_ok = True,mode=0o777)

                        if ("cfg.sv" in os.path.basename(design_file) ):
                            #print (f"FOund cgg.sv file, {design_file}")
                            shutil.copyfile(design_file, os.path.join(dest_path,block_name,( reference_folder if ref else implemented_folder ),os.path.basename(design_file)),follow_symlinks=True)
                        
                        #creating subfolders under src_backup/rtl/
                        file_path_trim = design_file.rsplit('/',1)
                        new_path = os.path.join(tc_rtl_path,file_path_trim[0].lstrip('/'))
                        os.makedirs(new_path,exist_ok = True,mode=0o777)
                        shutil.copyfile(design_file, os.path.join(new_path,os.path.basename(design_file)),follow_symlinks=True)
                        rtl_files +=1

                ##for .f files which might be read in
                f_file = re.search(r"fm\s*Command\s*:\s*read_sverilog\s*.* -f(.*) -",line,re.I)
                #rtl mode to copy files listed in rtllist file
                if(rtl_mode and not gate_mode and not upf and f_file is not None):
                    #creating src_backup/rtl
                    tc_rtl_path = os.path.join(dest_path,block_name,"src_backup","rtl")
                    if (not os.path.exists(tc_rtl_path)) :
                        os.makedirs(tc_rtl_path,exist_ok = True,mode=0o777)

                    design_file = f_file.groups()[0].strip()
                    if ("cfg.sv" in os.path.basename(design_file) ):
                        #print (f"FOund cgg.sv file, {design_file}")
                        shutil.copyfile(design_file, os.path.join(dest_path,block_name,( reference_folder if ref else implemented_folder ),os.path.basename(design_file)),follow_symlinks=True)
                    #creating subfolders under src_backup/rtl/
                    file_path_trim = design_file.rsplit('/',1)
                    new_path = os.path.join(tc_rtl_path,file_path_trim[0].lstrip('/'))
                    os.makedirs(new_path,exist_ok = True,mode=0o777)
                    shutil.copyfile(design_file, os.path.join(new_path,os.path.basename(design_file)),follow_symlinks=True)
                    rtl_files +=1

                done_reading = re.search(r"\s*INFO\s*:\s*Setup\s*",line,re.I)
                if(done_reading):
                    ref = False;impl = False;rtl_mode =False;gate_mode = False;design=False;upf = False;td_files = False

                #done copying impl and ref files
                td_constraints = re.search(r"Applying\s*TD\s*constraints.*",line,re.I)
                if(td_constraints):
                    td_files = True

                dop_mapping = re.search(r"INTEL_INFO\s*:\s*add_fm_clk_dop_mapping\s*procedure.*",line,re.I)
                if(dop_mapping):
                    td_files = True

                reset = re.search(r"\s*INFO\s*:\s*STEP\s*DONE\s*:\s*(match|verify)",line,re.I)
                if(reset):
                    td_files = False

                #copies all the "Script start" stuff
                script_start = re.match (r"INTEL_INFO\s*:\s*SCRIPT_START\s*:\s*(.*)\s*(\({1}|\[{1})",line,re.I)
                if(script_start):
                    script_file = script_start.groups()[0].split(" ")[0]
                    #print (f'{script_file}')
                    
                    #matches for *hookfiles* tag in namefile
                    name_match = re.search(r"(fev|user)_fm_.*",script_file.rsplit("/",1)[-1],re.I)
                    if(name_match):
                        print(f"{bcolors.OKGREEN}copied{bcolors.ENDC} {script_file.split('/')[-1]}", flush=True)
                        shutil.copyfile(script_file, os.path.join(dest_path,block_name,"scripts",task,os.path.basename(script_file)),follow_symlinks=True)
                    
                    #rtl 2stagelist copier - the list file
                    if(rtl_mode and not gate_mode and design):
                        print(f"{bcolors.OKGREEN}copied{bcolors.ENDC} {script_file.split('/')[-1]}", flush=True)
                        if (not ref and impl):
                            side_dir = os.path.join(dest_path,block_name,implemented_folder)
                        if (ref and not impl):
                            side_dir = os.path.join(dest_path,block_name,reference_folder)
                        if (not os.path.exists(side_dir)) :
                            os.makedirs(side_dir,exist_ok = True,mode=0o777)
                        shutil.copyfile(script_file,os.path.join(side_dir,os.path.basename(script_file)),follow_symlinks=True)
                        rtl_list_path_modifier(dest_path,block_name,script_file.split('/')[-1],side_dir)#this creates and modify the copied file
                        design_files +=1
                    
                    if(td_files):
                        print(f"{bcolors.OKGREEN}copied{bcolors.ENDC} {script_file.split('/')[-1]}", flush=True)
                        td_dir = os.path.join(dest_path,block_name,"td_collateral","icc2")
                        if (not os.path.exists(td_dir)) :
                            os.makedirs(td_dir,exist_ok = True,mode=0o777)
                        shutil.copyfile(script_file, os.path.join(td_dir,os.path.basename(script_file)),follow_symlinks=True)
                        design_files +=1

                    vars_detect = re.search(r"/scripts/vars.tcl",script_file,re.I)
                    if(vars_detect):
                        shutil.copyfile(script_file, os.path.join(dest_path,block_name,"scripts",os.path.basename(script_file)),follow_symlinks=True)
                    
                    hips_detect = re.search(r"hip_ivars.tcl",script_file,re.I)
                    if(hips_detect):
                        #shutil.copytree(script_file.rsplit('/',1)[0], os.path.join(dest_path,block_name),symlinks=False,dirs_exist_ok=True) 
                        os.system(f"cp -rf {script_file.rsplit('/',1)[0]} {os.path.join(dest_path,block_name)} ")
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(f"{exc_type}, {fname}, {exc_tb.tb_lineno}", flush=True)
        errorVar = True
        print(f"{bcolors.FAIL}Exception Encountered:{bcolors.ENDC} {e}", flush=True)
        with open("error.log","w") as error_log:
            error_log.write(f"{exc_type, fname, exc_tb.tb_lineno}\n")
        pass

    print (f"{bcolors.BOLD}{bcolors.OKGREEN}Extraction Completed.{bcolors.ENDC}", flush=True)
    print (f"{bcolors.BOLD}{bcolors.OKCYAN}Starting Post Porcessing{bcolors.ENDC}", flush=True)
    vars_creator(dest_path,block_name)
    id_creator(dest_path,block_name,tech,task,reference_folder,implemented_folder)
    
    


    print (f"\n{bcolors.OKCYAN}**STATS:**{bcolors.ENDC}", flush=True)
    print (f"{bcolors.HEADER}Liberty files copied:{bcolors.ENDC} {db_files}", flush=True)
    print (f"{bcolors.HEADER}rtl files copied:{bcolors.ENDC} {rtl_files}", flush=True)
    print (f"{bcolors.HEADER}UPF files copied:{bcolors.ENDC} {upf_files}", flush=True)
    print ( f"{bcolors.HEADER}Log File Size is:{bcolors.ENDC} {round(os.stat(log_path).st_size / (1024 * 1024),2)} MB", flush=True)
    print(f'{bcolors.HEADER}Number of Lines in the file is:{bcolors.ENDC} {count}\n', flush=True)



    end = timer()
    current, peak = tracemalloc.get_traced_memory()
    print(f"Total Time Elapsed: {round(end - start,2)}Sec", flush=True)
    print(f"Current memory usage is {current / 10**6}MB; Peak was {peak / 10**6}MB\n\n", flush=True)
    if (not errorVar) :
        print ( f"{bcolors.OKGREEN}Extraction Completed with no Errors.{bcolors.ENDC}\n", flush=True)
    else:
        print ( f"{bcolors.FAIL}Extraction Detected errors, fix them and Re-launch.{bcolors.ENDC}\n", flush=True)
    
    tracemalloc.stop()
    
    done = True
    
    


if __name__ == "__main__":
    flag = GracefulExiter()
    #this clears the console beofore start
    os.system('cls' if os.name == 'nt' else 'clear')
    main(sys.argv)
    #this causes the graceful exit
    if flag.exit():
        print ( f"{bcolors.FAIL}ctrl+c eceived again.Exitting{bcolors.ENDC}", flush=True)
        exit(1)

