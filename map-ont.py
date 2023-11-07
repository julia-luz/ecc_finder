#!/usr/bin/env python3

"""
# June 2021
# If using this pipeline please cite : XXXXXXXXXX
#--------------------------------------------------------------------------+    
#                                                   
#	ecc_finder is a tool 
#       to detect eccDNA using Illumina and ONT sequencing.  
#                                                        
#--------------------------------------------------------------------------+
#                                                      
#	AUTHOR: panpan ZHANG                            
#	CONTACT: njaupanpan@gmail.com                      
#                                                         
#	LICENSE:                                            
# 	GNU General Public License, Version 3               
#	http://www.gnu.org/licenses/gpl.html  
#                                             
#	VERSION: v1.0.0                  
#                                                                                                       
#--------------------------------------------------------------------------+
"""

import os
import sys
import glob
import argparse
import multiprocessing
import subprocess

import pysam
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
os.environ['XDG_SESSION_TYPE'] = 'x11'

from eccFinder_lib.utilities import log,run_oae,get_eccFinder_version
from eccFinder_lib.Aligner import Minimap2SAMAligner
from eccFinder_lib.Aligner import Minimap2Aligner
from eccFinder_lib.Spliter import tidehunter
from eccFinder_lib.Peaker import genrich

def read_genome_alignments(file_prefix,align_path,min_qlen,min_aln,overwrite_files):
    """ Filtering the raw read alignments based on query length and alignment length."""
    if os.path.isfile(align_path + file_prefix+".paf.bed"):
        if not overwrite_files:
            log("INFO", "Retaining pre-existing file: " + align_path +file_prefix+".paf.bed")
        else:
            log("INFO", "Overwriting pre-existing file: " + align_path +file_prefix+".paf.bed")
            with open(align_path + file_prefix+".paf") as f:   
                outfile=open(align_path + file_prefix+".paf.bed",'w')
                headers = ['refID','rstart', 'rend','queryID','qlen','direction']
                total=0
                n_primary=0
                for line in f: 
                    parts = line.strip().split("\t")
                    total=total+1
                    resultss = {
		            "queryID": parts[0],
		            "qlen":  int(parts[1]),
		            "qstart": int(parts[2]),
		            "qend": int(parts[3]),
		            "direction": parts[4],
		            "refID": parts[5],
		            "rlen": int(parts[6]),
		            "rstart": int(parts[7]),
		            "rend": int(parts[8]),
                    "rdis": int(parts[8])-int(parts[7]),
		            "allmatch": int(parts[9]),
                    "blockmatch": int(parts[10]),
                    }
                    if min_aln is not None and resultss['rdis'] < min_aln:
                        n_primary=n_primary+1
                        continue
                    if min_qlen is not None and resultss['qlen'] < min_qlen:
                        continue
                    out_row = (str(resultss[x]) for x in headers)
                    outfile.write('\t'.join(out_row))
                    outfile.write('\n')
    else:
        with open(align_path + file_prefix+".paf") as f:   
            outfile=open(align_path + file_prefix+".paf.bed",'w')
            headers = ['refID','rstart', 'rend','queryID','qlen','direction']
            total=0
            n_primary=0
            for line in f: 
                parts = line.strip().split("\t")
                total=total+1
                resultss = {
		        "queryID": parts[0],
		        "qlen":  int(parts[1]),
		        "qstart": int(parts[2]),
		        "qend": int(parts[3]),
		        "direction": parts[4],
		        "refID": parts[5],
		        "rlen": int(parts[6]),
		        "rstart": int(parts[7]),
		        "rend": int(parts[8]),
                "rdis": int(parts[8])-int(parts[7]),
		        "allmatch": int(parts[9]),
                "blockmatch": int(parts[10]),
                }
                if min_aln is not None and resultss['rdis'] < min_aln:
                    n_primary=n_primary+1
                    continue
                if min_qlen is not None and resultss['qlen'] < min_qlen:
                    continue
                out_row = (str(resultss[x]) for x in headers)
                outfile.write('\t'.join(out_row))
                outfile.write('\n')

def run_TideHunter(file_prefix,query_file,peak_path, num_threads, max_divergence,min_period_size,num_copies,overwrite_files):
    """ Spliting tandem repeats in one long read. """
    if os.path.isfile(peak_path +file_prefix+".unit.fa"):
        if not overwrite_files:
            log("INFO", "Retaining pre-existing file: " + peak_path +file_prefix+".unit.fa")
        else:
            log("INFO", "Overwriting pre-existing file: " +peak_path +file_prefix+".unit.fa")
            TH_params = " -c "+ str(num_copies)
            TH_params += " -t " + str(num_threads) +" -e " +str(max_divergence) +" -p " + str(min_period_size)+ " -P 1000000 "
            TH_cmd = "TideHunter"+ TH_params+ str(query_file)+ " -u > "+ peak_path +file_prefix+".unit.fa"
            subprocess.call(TH_cmd, shell=True) 
    else:  
        TH_params = " -c "+ str(num_copies)
        TH_params += " -t " + str(num_threads) +" -e " +str(max_divergence) +" -p " + str(min_period_size)+ " -P 1000000 "
        TH_cmd = "TideHunter"+ TH_params+ str(query_file)+ " -u > "+ peak_path +file_prefix+".unit.fa"
        subprocess.call(TH_cmd, shell=True) 

def run_samtools(file_prefix,output_path,peak_path,num_threads,overwrite_files):
    """ sort, filter and index alignments. """
    if os.path.isfile(peak_path +file_prefix+".unit.bam"):
        if not overwrite_files:
            log("INFO", "Retaining pre-existing file: " + peak_path +file_prefix+".unit.bam")
        else:
            log("INFO", "Overwriting pre-existing file: " + peak_path +file_prefix+".unit.bam")
            pysam.sort("-@", str(num_threads),"-n",  "-o", output_path+"tmp1", output_path +file_prefix+".tmp.sam", catch_stdout=False)
            pysam.view("-@", str(num_threads),"-h", "-o", output_path+"tmp2",output_path +"tmp1", catch_stdout=False)
            cmd = "awk -v OFS='\\t' '{if ($1 !~ /^@/ )$1=$1\"/2\"}1' " + output_path+"tmp2" + ">"+ peak_path +file_prefix+".unit.bam"
            subprocess.call(cmd, shell=True)
    else:
        pysam.sort("-@", str(num_threads),"-n",  "-o", output_path+"tmp1", output_path +file_prefix+".tmp.sam", catch_stdout=False)
        pysam.view("-@", str(num_threads),"-h", "-o", output_path+"tmp2",output_path +"tmp1", catch_stdout=False)
        cmd = "awk -v OFS='\\t' '{if ($1 !~ /^@/ )$1=$1\"/2\"}1' " + output_path+"tmp2" + ">"+ peak_path +file_prefix+".unit.bam"
        subprocess.call(cmd, shell=True)

def run_Genrich(file_prefix,output_path,peak_path,min_peak,max_dist,max_pvalue,overwrite_files):
    """ Detecting sites of genomic enrichment. """
    if os.path.isfile(output_path +file_prefix+".site.bed"):
        if not overwrite_files:
            log("INFO", "Retaining pre-existing file: " + output_path +file_prefix+".site.bed")
        else:
            log("INFO", "Overwriting pre-existing file: " + output_path +file_prefix+".site.bed")
            GR_params = " -yv "
            GR_params += " -l " + str(min_peak)+" -g " + str(max_dist) +" -p " + str(max_pvalue) 
            GR_cmd = "Genrich -t "+ peak_path +file_prefix+".unit.bam" + GR_params+ " -o "+ peak_path +file_prefix+".site"
            subprocess.call(GR_cmd, shell=True) 
            cmd1 = "cut -f1-3 " + peak_path +file_prefix+".site" + " > " +output_path +file_prefix+".site.bed"
            os.popen("{inS} ".format(inS=cmd1))
    else:    
        GR_params = " -yv "
        GR_params += " -l " + str(min_peak)+" -g " + str(max_dist) +" -p " + str(max_pvalue)    
        GR_cmd = "Genrich -t "+peak_path +file_prefix+".unit.bam" + GR_params+ " -o "+ peak_path +file_prefix+".site"
        subprocess.call(GR_cmd, shell=True) 
        cmd1 = "cut -f1-3 " + peak_path +file_prefix+".site" + " > " +output_path +file_prefix+".site.bed"
        os.popen("{inS} ".format(inS=cmd1))

def run_filterBED(file_prefix,output_path, align_path,min_read,min_bound,min_cov,overwrite_files):
    if os.path.isfile(output_path +file_prefix +".csv"):
        if not overwrite_files: 
            log ("INFO", "Retaining pre-existing file: " + output_path +file_prefix +".csv")
        else:
            log ("INFO", "Overwriting pre-existing file: " + output_path +file_prefix +".csv")
            bedtools_params= " -wao -f "+ str(min_bound) 
            tmp1=output_path +file_prefix+".paf.bed.tmp1"
            cmd ="bedtools intersect -a "+ output_path +file_prefix+".site.bed -b " + align_path +file_prefix + ".paf.bed" + bedtools_params+ " -nonamecheck > "+tmp1
            subprocess.call(cmd, shell=True) 

            cmd1 = "cat "+ output_path +file_prefix+".paf.bed.tmp1"
            cmd2 = "awk '$10>0'| sort -k7,7 -k9,9 | groupBy -g 1,2,3,7,9 -c 7 -o count |awk '$6>1'"
            cmd3 = "bedtools sort |groupBy -g 1,2,3 -c 4,6 -o count_distinct,sum -nonamecheck|awk '$4>2' > " +output_path +file_prefix+".paf.bed.tmp2"
            sub = "{inS} |{group}|{bed} ".format(inS=cmd1, group=cmd2, bed=cmd3)
            ps = subprocess.Popen(sub,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            output = ps.communicate()[0]

            log("INFO", "Filtering locus by boundary coverage. ")
            csv=output_path +file_prefix +".tmp.csv"
            cmd ="bedtools coverage -counts -a "+ output_path +file_prefix+".paf.bed.tmp2 -b " + align_path +file_prefix + ".paf.bed -f " + str(min_bound)+ " -nonamecheck > "+csv
            subprocess.call(cmd, shell=True) 

            # Write the ecc_finder.csv.
            log("INFO", "Filtering locus by mininum number of tandely repeated long reads ")
            with open(output_path + file_prefix+".tmp.csv") as f:   
                outfile=open(output_path + file_prefix+".csv",'w')
                headers = ['refID','rstart','rend','read_number','repeat_unit','coverage','ecc_len']
                total=0
                n_primary=0
                for line in f:
                    parts = line.strip().split("\t")
                    total=total+1
                    resultss = {
	                "refID": parts[0],
	                "rstart":  int(parts[1]),
	                "rend": int(parts[2]),
	                "read_number": int(parts[3]),
	                "repeat_unit": parts[4],
                    "coverage": int(parts[4]),
                    "ecc_len":int(parts[2])-int(parts[1]),
                    }
                    if min_read is not None and resultss['read_number'] < min_read:
                        n_primary=n_primary+1
                        continue
                    if min_cov is not None and resultss['coverage'] < min_cov:
                        continue
                    out_row = (str(resultss[x]) for x in headers)
                    outfile.write('\t'.join(out_row))
                    outfile.write('\n')

            for filename in glob.glob(os.path.join(output_path, "*tmp*")):
                try:
                    #Trying to remove a current file
                    os.remove(os.path.join(output_path, filename))
                except EnvironmentError:
                    #You don't have permission to do it
                    pass
    else:
        log("INFO", "Filtering locus by repeat units in one read") 
        bedtools_params= " -wao -f "+ str(min_bound) 
        tmp1=output_path +file_prefix+".paf.bed.tmp1"
        cmd ="bedtools intersect -a "+ output_path +file_prefix+".site.bed -b " + align_path +file_prefix + ".paf.bed" + bedtools_params+ " -nonamecheck > "+tmp1
        subprocess.call(cmd, shell=True) 

        cmd1 = "cat "+ output_path +file_prefix+".paf.bed.tmp1"
        cmd2 = "awk '$10>0'| sort -k7,7 -k9,9 | groupBy -g 1,2,3,7,9 -c 7 -o count |awk '$6>1'"
        cmd3 = "bedtools sort |groupBy -g 1,2,3 -c 4,6 -o count_distinct,sum -nonamecheck|awk '$4>2' > " +output_path +file_prefix+".paf.bed.tmp2"
        sub = "{inS} |{group}|{bed} ".format(inS=cmd1, group=cmd2, bed=cmd3)
        ps = subprocess.Popen(sub,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        output = ps.communicate()[0]

        log("INFO", "Filtering locus by boundary coverage. ")
        csv=output_path +file_prefix +".tmp.csv"
        cmd ="bedtools coverage -counts -a "+ output_path +file_prefix+".paf.bed.tmp2 -b " + align_path +file_prefix + ".paf.bed -f " + str(min_bound)+ " -nonamecheck > "+csv
        subprocess.call(cmd, shell=True) 

        # Write the ecc_finder.csv.
        log("INFO", "Filtering locus by mininum number of tandely repeated long reads ")
        with open(output_path + file_prefix+".tmp.csv") as f:   
            outfile=open(output_path + file_prefix+".csv",'w')
            headers = ['refID','rstart','rend','read_number','repeat_unit','coverage','ecc_len']
            total=0
            n_primary=0
            for line in f: 
                log ("INFO", line)
                parts = line.strip().split("\t")
                total=total+1
                resultss = {
	            "refID": parts[0],
	            "rstart":  int(parts[1]),
	            "rend": int(parts[2]),
	            "read_number": int(parts[3]),
	            "repeat_unit": parts[4],
                "coverage": int(parts[4]),
                "ecc_len":int(parts[2])-int(parts[1])
                }
                if min_read is not None and resultss['read_number'] < min_read:
                    n_primary=n_primary+1
                    continue
                if min_cov is not None and resultss['coverage'] < min_cov:
                    continue
                out_row = (str(resultss[x]) for x in headers)
                outfile.write('\t'.join(out_row))
                outfile.write('\n')

        for filename in glob.glob(os.path.join(output_path, "*tmp*")):
            try:
                #Trying to remove a current file
                os.remove(os.path.join(output_path, filename))
            except EnvironmentError:
                #You don't have permission to do it
                pass

def run_getFasta(output_path, file_prefix ,ref_genome,overwrite_files):
    if os.path.isfile(output_path +file_prefix +".fasta"):
        if not overwrite_files:
            log("INFO", "Retaining pre-existing file: " + output_path +file_prefix+".fasta")
        else:
            log("INFO", "Overwriting pre-existing file: " + output_path +file_prefix+".fasta")
            cmd ="seqtk subseq "+ ref_genome+ " " + output_path +file_prefix +".csv" + "> "+output_path +file_prefix +".fasta"
            subprocess.call(cmd, shell=True) 
    else: 
        cmd ="seqtk subseq "+ ref_genome+ " " + output_path +file_prefix +".csv" + "> "+output_path +file_prefix +".fasta"
        subprocess.call(cmd, shell=True)

def main():
    description = "A tool to detect eccDNA loci using ONT sequencing"
    parser = argparse.ArgumentParser(description=description, usage="ecc_finder.py map-ont <reference.idx> <query.fq> -r <reference.fa> (option)")
    parser.add_argument("idx", metavar="<reference.idx>", nargs='?', default="", type=str, help="index file of reference genome")
    parser.add_argument("query", metavar="<query.fq>", nargs='?', default="", type=str, help="query fastq/fasta file (uncompressed or bgzipped)")
    parser.add_argument("-r", metavar="<query.fasta>", default="", type=str, help="reference genome fasta file (uncompressed or bgzipped)")

    map_options = parser.add_argument_group("map options")   
    map_options.add_argument('-t', metavar="INT",type=int, default=get_default_thread(), help='number of CPU threads for mapping mode')
    mm2_default = "-x map-ont"

    map_options.add_argument("-g", metavar="STR", type=str, default="", help="reference genome size larger than 4Gb [yes]")
    map_options.add_argument("-q", metavar="INT", type=int, default=200, help="minimum query length [200]")
    map_options.add_argument("-a", metavar="INT", type=int, default=200, help="minimum alignment length [200]")
    map_options.add_argument("--five-prime",metavar="STR", type=str, help="5' adapter sequence (sense strand) [NULL]")
    map_options.add_argument("--three-prime",metavar="STR", type=str, help="3' adapter sequence (anti-sense strand) [NULL]")

    peak_options = parser.add_argument_group("peak-calling options")
    peak_options.add_argument("-l", metavar="INT", type=int, default=200, help="minimum length of a peak [200]")
    peak_options.add_argument("-d", metavar="INT", type=int, default=100, help="maximum distance between signif. sites [1000]")
    peak_options.add_argument("-p", metavar="FLT", type=float, default=0.05, help="maximum p-value [0.05]")

    val_options = parser.add_argument_group("validation options")
    val_options.add_argument("-n", metavar="INT", type=int, default=2, help="minimum copy number of tandmin_boundem repeat in a long read [2]")
    val_options.add_argument("-e", metavar="FLT", type=float, default=0.25, help="maximum allowed divergence rate between two consecutive repeats [0.25]")
    val_options.add_argument("-s", metavar="INT", type=int, default=30, help="minimum period size of tandem repeat (>=2) [30]")
    val_options.add_argument("--min-read", metavar="INT", type=int, default=3, help="filter locus by unique mapped read number [3]")
    val_options.add_argument("--min-bound", metavar="FLT", type=float, default=0.8, help="filter locus at regions by boundary coverage (# aligned bases / boundary bases)[0.8]")
    val_options.add_argument("--min-cov", metavar="FLT", type=float, default=10, help="minimum coverage of detected eccDNA loci [10]")

    out_options = parser.add_argument_group("output options")
    out_options.add_argument("-o", metavar="PATH", type=str, default="eccFinder_output", help="output directory [./eccFinder_output]")
    out_options.add_argument("-w", action='store_true', default=False, help="overwrite intermediate files")
    out_options.add_argument("-x", type=str, default="ecc.ont", help="add prefix to output [ecc.ont]")
    out_options.add_argument("--debug", action='store_true', default=False, help=argparse.SUPPRESS)

    args = parser.parse_args()

    if not args.idx or not args.query or not args.r:
        parser.print_help()
        sys.exit("\n** The reference fasta, idx and query files are required **")

    log("VERSION", "ecc_finder " + get_eccFinder_version())
    log("CMD", "python ecc_finder.py map-ont " + " ".join(sys.argv[1:]))

    idx_file = os.path.abspath(args.idx)
    query_file = os.path.abspath(args.query)
    ref_genome = args.r

    if not os.path.isfile(idx_file):
        raise FileNotFoundError("Could not find file: %s" % idx_file)
    if not os.path.isfile(query_file):
        raise FileNotFoundError("Could not find file: %s" % query_file)
    if not ref_genome:
        raise FileNotFoundError("Could not find file: %s" % ref_genome)

    num_threads = args.t
    min_qlen = args.q
    min_aln = args.a
    five_prime = args.five_prime
    three_prime = args.three_prime

    min_peak=args.l
    max_dist =args.d
    max_pvalue =args.p

    num_copies = args.n
    max_divergence = args.e
    min_period_size = args.s
    min_read= args.min_read
    min_bound = args.min_bound
    min_cov = args.min_cov

    if min_read < 0:
        if min_read != -1:
            raise ValueError("--min-read must be >=3")
    if min_bound < 0:
        if min_bound != -1:
            raise ValueError("--min-cov must be >=0")
    if ref_genome:
        ref_genome=os.path.abspath(ref_genome)
    if five_prime:
        five_prime=os.path.abspath(five_prime)
    if three_prime:
        three_prime=os.path.abspath(three_prime)

    output_path = args.o
    if not os.path.isdir(output_path):
        os.mkdir(output_path)
    output_path = os.path.abspath(output_path) + "/"
    overwrite_files = args.w
    file_prefix = args.x

    align_path = os.path.abspath(args.o) + "/align_files/"
    if not os.path.isdir(output_path+"align_files/"):
        os.makedirs(output_path+"align_files/")
    align_path = os.path.abspath(args.o) + "/align_files/"

    peak_path = os.path.abspath(args.o) + "/peak_files/"
    if not os.path.isdir(output_path+"peak_files/"):
        os.makedirs(output_path+"peak_files/")
    peak_path = os.path.abspath(args.o) + "/peak_files/"


    # Debugging options
    #debug_mode = args.debug

    #Align the query raw read to the reference.
    log("INFO","Align the query raw read to the reference.")
    mm2_params = mm2_default
    mm2_params += " -t " + str(num_threads)
    mapont_aligner_path = "minimap2"
    log("INFO", "Mapping the query raw read to the reference genome")
    map_all = Minimap2Aligner(idx_file, [query_file],mapont_aligner_path, mm2_params,align_path + file_prefix , in_overwrite=overwrite_files)
    print(map_all)
    map_all.run_aligner()

    #Filter raw read alignments based on query length and alignment length
    log("INFO", "Filtering read alignments based on query length and alignment length")
    read_genome_alignments(file_prefix,align_path,min_qlen,min_aln, overwrite_files)

    #Splitting into unit sequences of each tandem repeat for a long read   
    log("INFO", "Detecting tandem repeat pattern from long reads")
    run_TideHunter(file_prefix,query_file,peak_path, num_threads, max_divergence,min_period_size,num_copies,overwrite_files)

    #Peak calling
    log("INFO", "Peak calling for reads with the tandem repeated pattern")
    minimap2_params ="-ax map-ont"
    mapont_aligner_path="minimap2"
    mm2_params = minimap2_params +" -t " + str(num_threads)
    pre= output_path + file_prefix+".tmp"
    map_all = Minimap2SAMAligner(idx_file, [peak_path +file_prefix+".unit.fa"],mapont_aligner_path, mm2_params,pre , in_overwrite=overwrite_files)
    map_all.run_aligner()

    run_samtools(file_prefix,output_path,peak_path,num_threads,overwrite_files)
    run_Genrich(file_prefix,output_path,peak_path,min_peak,max_dist,max_pvalue,overwrite_files)

    #Peak calling
    log("INFO", "Producing bed file of eccDNA locus")
    run_filterBED(file_prefix,output_path, align_path,min_read,min_bound,min_cov,overwrite_files)

    log("INFO", "Producing fasta file of eccDNA locus")
    run_getFasta(output_path, file_prefix ,ref_genome,overwrite_files)

    log("INFO", "Plotting size distribution of detected eccDNA")

    d=pd.read_csv(output_path +file_prefix+".csv", sep='\t',header=None,names=['chr','rstart','rend','num','unit','cov','len'])
    #bins = [100, 200, 400, 600,1000,2000,3000,4000,5000,6000,7000,8000,9000,10000]
    x=[k for k in d.len]
    plt.hist(x, color='orange')
    plt.ylabel('Count')
    plt.xlabel('Size distribution')
    plt.show(block=False)
    plt.savefig(output_path +file_prefix+".distribution.png")

    log("INFO", "Finished running ecc_finder")
    log("INFO", "Goodbye, have a nice day!")

def get_default_thread():
    return min(multiprocessing.cpu_count(), 8)

if __name__ == '__main__':
    main()
