#!/usr/bin/env python3
"""
Tool for computing stats on a TR VCF file
"""

# Allow making plots even with no x-forward
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt

# Allow plots to be editable in Adobe Illustrator
import matplotlib
matplotlib.rcParams['pdf.fonttype'] = 42
matplotlib.rcParams['ps.fonttype'] = 42

# Imports
import argparse
import os
import sys
import time
from typing import List

import numpy as np

import trtools.utils.common as common
import trtools.utils.tr_harmonizer as trh
import trtools.utils.utils as utils
from trtools import __version__

MAXPLOTS = 10 # don't plot more than this many allele freqs

def PlotAlleleFreqs(trrecord, outprefix, samplelists=None, sampleprefixes=None):
    r"""Plot allele frequencies for a locus

    Parameters
    ----------
    trrecord: trh.TRRecord object
          The record that we are computing the statistic for
    outprefix : str
          Prefix for output file
    samplelists: list of list of str, optional
          List of lists of the samples that we include when compute the statistic
    sampleprefixes : list of str, optional
          Prefixes for each sample list to use in legend
    """
    if samplelists is None or samplelists == []:
        samplelists = [None]
        sampleprefixes = ["sample"]
    allele_freqs_list = []
    allele_set = set()
    for sl in samplelists:
        afreqs = trrecord.GetAlleleFreqs(uselength=True, samplelist=sl)
        allele_freqs_list.append(afreqs)
        allele_set = allele_set.union(afreqs.keys())
    min_allele = min(allele_set)-2
    max_allele = max(allele_set)+2
    bins = np.arange(min_allele, max_allele, 1)

    fname = outprefix + "-%s-%s.pdf"%(trrecord.vcfrecord.CHROM, trrecord.vcfrecord.POS)
    w = 1.0/(len(samplelists)+0.3)
    fig = plt.figure()
    ax = fig.add_subplot(111)
    for i in range(len(samplelists)):
        ax.bar([item+i*w for item in bins], [allele_freqs_list[i].get(item, 0) for item in bins],
               label=sampleprefixes[i], width=w*1.1)
    ax.legend()
    ax.set_xlabel("TR allele (num. %s rpts)"%trrecord.motif, size=15)
    ax.set_ylabel("Frequency", size=15)
    ax.set_xticklabels([int(item) for item in ax.get_xticks()], size=12)
    ax.set_yticklabels(["%.2f"%item for item in ax.get_yticks()], size=12)
    fig.tight_layout()
    fig.savefig(fname)
    plt.close()

def GetHeader(header, sample_prefixes):
    r"""Return header items for a column

    Parameters
    ----------
    header : str
       Header item
    sample_prefixes : list of str
       List of sample prefixes. empty if no sample groups used

    Returns
    -------
    header_items : list of str
       List of header items
    """
    if len(sample_prefixes) == 0: return [header]
    else:
        header_items = []
        for sp in sample_prefixes:
            header_items.append(header+"-"+sp)
        return header_items

def GetThresh(trrecord: trh.TRRecord, samplelists: List[List[str]] = []) -> List[float]:
    """Return the maximum TR allele length observed

    Parameters
    ----------
    trrecord:
        The record that we are computing the statistic for
    samplelists:
          List of lists of the samples that we include when compute the statistic

    Returns
    -------
    thresh: List[float]
          List of Maximum allele length observed in each sample group,
          or nan if no alleles called
    """
    if len(samplelists) == 0:
        return [trrecord.GetMaxAllele()]
    else:
        return [trrecord.GetMaxAllele(samplelist=sl) for sl in samplelists]

def GetAFreq(trrecord: trh.TRRecord,
             samplelists: List[List[str]] = [],
             count: bool = False,
             uselength: bool = True) -> List[str]:
    """Return allele frequency for a TR

    Parameters
    ----------
    trrecord:
          The record that we are computing the statistic for
    samplelist:
          List of lists of the samples that we include when compute the statistic
          If [], then include all samples in a single group
    count:
          If True, return allele counts rather than allele frequencies
    uselength:
          Whether we should collapse alleles by length

    Returns
    -------
    allele_freqs_strs: list of str
          Format: allele1:freq1,allele2:freq2,etc. for each sample group
          Only alleles with more than one call in a group are reported for
          that group. Groups with no called alleles are reported as '.'
    """
    if len(samplelists) == 0:
        samplelists.append(None)
    allele_freqs_strs = []
    for sl in samplelists:
        if count:
            allele_counts = trrecord.GetAlleleCounts(uselength=uselength, samplelist=sl)
            if len(allele_counts.keys()) == 0:
                allele_freqs_strs.append(".")
            else:
                allele_freqs_strs.append(",".join(["%s:%i"%(a, allele_counts.get(a, 0)) for a in sorted(allele_counts.keys())]))
        else:
            allele_freqs = trrecord.GetAlleleFreqs(uselength=uselength, samplelist=sl)
            if len(allele_freqs.keys()) == 0:
                allele_freqs_strs.append(".")
            else:
                allele_freqs_strs.append(",".join(["%s:%.3f"%(a, allele_freqs.get(a, 0)) for a in sorted(allele_freqs.keys())]))
    return allele_freqs_strs

def GetHWEP(trrecord: trh.TRRecord,
            samplelists: List[List[str]] = [],
            uselength: bool = True) -> List[float]:
    """Compute Hardy Weinberg p-value

    Tests whether the number of observed heterozygous vs.
    homozygous individuals is different than expected
    under Hardy Weinberg Equilibrium given the observed
    allele frequencies, based on a binomial test.

    Parameters
    ----------
    trrecord:
          The record that we are computing the statistic for
    samplelist:
          List of list of the samples that we include when compute the statistic
    uselength:
          Whether we should collapse alleles by length

    Returns
    -------
    p-value: list of float
          The two-sided p-value returned by a binomial test (scipy.stats.binom_test)
          If there are no calls, return np.nan
          If the genotype alleles not included in frequencies dictionary, return np.nan
          One value returned for each samplelist
    """
    if len(samplelists)==0: samplelists.append(None)
    pvals = []
    for sl in samplelists:
        allele_freqs = trrecord.GetAlleleFreqs(samplelist=sl, uselength=uselength)
        genotype_counts = trrecord.GetGenotypeCounts(samplelist=sl, uselength=uselength)
        pvals.append(utils.GetHardyWeinbergBinomialTest(allele_freqs, genotype_counts))
    return pvals

def GetHet(trrecord: trh.TRRecord,
            samplelists: List[List[str]] = [],
            uselength: bool = True) -> List[float]:
    """Compute heterozygosity of a locus

    Heterozygosity is defined as the probability
    that two randomly drawn allele are different.

    Parameters
    ----------
    trrecord:
          The record that we are computing the statistic for
    samplelist:
          List of list of the samples that we include when compute the statistic
    uselength:
          Whether we should collapse alleles by length

    Returns
    -------
    heterozygosity: List[float]
          For each sample list, the heterozypostiy of the calls for those
          samples, or np.nan if no such calls
    """
    if len(samplelists) == 0: samplelists.append(None)
    hetvals = []
    for sl in samplelists:
        allele_freqs = trrecord.GetAlleleFreqs(samplelist=sl, uselength=uselength)
        hetvals.append(utils.GetHeterozygosity(allele_freqs))
    return hetvals

def GetEntropy(trrecord: trh.TRRecord,
               samplelists: List[List[str]] = [],
               uselength: bool = True) -> List[float]:
    """Compute the entropy of a locus

    This is the (bit) entropy of the distribution of alleles
    called at that locus. See `wikipedia
    <https://en.wikipedia.org/wiki/Entropy_(information_theory)>`_
    for the definition of entropy.

    Parameters
    ----------
    trrecord:
          The record that we are computing the statistic for
    samplelist:
          List of list of the samples that we include when compute the statistic
    uselength:
          Whether we should collapse alleles by length

    Returns
    -------
    heterozygosity: List[float]
          For each sample list, the entropy of the calls for those
          samples, or np.nan if no such calls
    """
    if len(samplelists) == 0: samplelists.append(None)
    entropy_vals = []
    for sl in samplelists:
        allele_freqs = trrecord.GetAlleleFreqs(samplelist=sl, uselength=uselength)
        entropy_vals.append(utils.GetEntropy(allele_freqs))
    return entropy_vals

def GetMean(trrecord: trh.TRRecord,
            samplelists: List[List[str]] = [],
            uselength: bool = True) -> List[float]:
    """Compute the mean allele length

    Parameters
    ----------
    trrecord:
          The record that we are computing the statistic for
    samplelist:
          List of list of the samples that we include when compute the statistic

    Returns
    -------
    mean: List[float]
          For each sample list, the mean allele length, or np.nan if no
          calls for that sample
    """

    if len(samplelists) == 0:
        samplelists.append(None)
    return [utils.GetMean(trrecord.GetAlleleFreqs(samplelist=sl, uselength=True))
            for sl in samplelists]

def GetMode(trrecord: trh.TRRecord,
            samplelists: List[List[str]] = [],
            uselength: bool = True) -> List[float]:
    """Compute the mode of the allele lengths

    Parameters
    ----------
    trrecord:
          The record that we are computing the statistic for
    samplelist:
          List of list of the samples that we include when compute the statistic

    Parameters
    ----------
    trrecord: trh.TRRecord object
          The record that we are computing the statistic for
    samplelist: list of list of str
          List of the samples that we include when compute the statistic

    Returns
    -------
    mean: List[float]
          For each sample list, the mode allele length, or np.nan if no
          calls for that sample
    """

    if len(samplelists) == 0: samplelists.append(None)
    return [utils.GetMode(trrecord.GetAlleleFreqs(samplelist=sl, uselength=True)) for sl in samplelists]

def GetVariance(trrecord: trh.TRRecord,
                samplelists: List[List[str]] = [],
                uselength: bool = True) -> List[float]:
    """Compute the variance of the allele lengths

    Parameters
    ----------
    trrecord:
          The record that we are computing the statistic for
    samplelists:
          List of list of the samples that we include when compute the statistic

    Returns
    -------
    variance: List[float]
          For each sample list, the variance of the allele lengths, or np.nan if
          no calls for that sample
    """

    if len(samplelists) == 0: samplelists.append(None)
    return [utils.GetVariance(trrecord.GetAlleleFreqs(samplelist=sl, uselength=True)) for sl in samplelists]

def GetNumSamples(trrecord, samplelists=[]):
    r"""Compute the number of samples

    Parameters
    ----------
    trrecord: trh.TRRecord object
          The record that we are computing the statistic for
    samplelist: list of list of str
          List of list of the samples that we include when compute the statistic

    Returns
    -------
    numSamples: list of int
          The number of samples. One value for each sample list
          If the allele frequencies dictionary is invalid, return np.nan
    """
    if len(samplelists) == 0: samplelists.append(None)
    return [sum(trrecord.GetGenotypeCounts(samplelist=sl).values()) for sl in samplelists]

def getargs(): # pragma: no cover
    parser = argparse.ArgumentParser(
        __doc__,
        formatter_class=utils.ArgumentDefaultsHelpFormatter
    )
    inout_group = parser.add_argument_group("Input/output")
    inout_group.add_argument("--vcf", help="Input STR VCF file", type=str, required=True)
    inout_group.add_argument(
        "--out",
        help=("Output file prefix. Use stdout to print file to standard "
              "output. In addition, if not stdout then timing diagnostics are print to "
              "stdout."),
        type=str,
        required=True
    )
    inout_group.add_argument("--vcftype", help="Options=%s"%[str(item) for item in trh.VcfTypes.__members__], type=str, default="auto")
    inout_group.add_argument(
        "--precision",
        help=("How much precision to use when printing decimals",
        type=int,
        default=3
     )
    filter_group = parser.add_argument_group("Filtering group")
    filter_group.add_argument("--samples", help="File containing list of samples to include. Or a comma-separated list of files to compute stats separate for each group of samples", type=str)
    filter_group.add_argument("--sample-prefixes", help="Prefixes to name output for each samples group. By default uses 1,2,3 etc.", type=str)
    filter_group.add_argument("--region", help="Restrict to the region "
                              "chrom:start-end. Requires file to bgzipped and"
                              " tabix indexed.", type=str)
    stat_group_name = "Stats group"
    stat_group = parser.add_argument_group(stat_group_name)
    stat_group.add_argument("--thresh", help="Output threshold field (max allele size, used for GangSTR strinfo).", action="store_true")
    stat_group.add_argument("--afreq", help="Output allele frequencies", action="store_true")
    stat_group.add_argument("--acount", help="Output allele counts", action="store_true")
    stat_group.add_argument("--hwep", help="Output HWE p-values per loci.", action="store_true")
    stat_group.add_argument("--het", help="Output the heterozygosity of each locus.", action="store_true")
    stat_group.add_argument("--entropy", help="Output the entropy of each locus.", action="store_true")
    stat_group.add_argument("--mean", help="Output mean of the allele frequencies.", action="store_true")
    stat_group.add_argument("--mode", help="Output mode of the allele frequencies.", action="store_true")
    stat_group.add_argument("--var", help="Output variance of the allele frequencies.", action="store_true")
    stat_group.add_argument("--numcalled", help="Output number of samples called.", action="store_true")
    stat_group.add_argument("--use-length", help="Calculate per-locus stats (het, HWE) collapsing alleles by length. This is implicitly true for genotypers which only emit length based genotypes.", action="store_true")
    plot_group = parser.add_argument_group("Plotting group")
    plot_group.add_argument("--plot-afreq", help="Output allele frequency plot. Will only do for a maximum of 10 TRs.", action="store_true")
    ver_group = parser.add_argument_group("Version")
    ver_group.add_argument("--version", action="version", version = '{version}'.format(version=__version__))
    args = parser.parse_args()
    # If no stat selected, print an error message and terminate
    stat_dict = {}
    for grp in parser._action_groups:
        if grp.title == stat_group_name:
            stat_dict = {a.dest:getattr(args,a.dest,None) for a in grp._group_actions}

    if not any(stat_dict.values()):
        common.WARNING("Error: Please use at least one of the flags in the Stats group. See statSTR --help for options.")
        return None
    return args

def format_nan_precision(precision_format, val):
    if np.isnan(val):
        return "\tnan"
    else:
        return precision_format.format(val)

def main(args):
    if not os.path.exists(args.vcf):
        common.WARNING("Error: %s does not exist"%args.vcf)
        return 1

    if not os.path.exists(os.path.dirname(os.path.abspath(args.out))):
        common.WARNING("Error: The directory which contains the output location {} does"
                       " not exist".format(args.out))
        return 1

    if os.path.isdir(args.out) and args.out.endswith(os.sep):
        common.WARNING("Error: The output location {} is a "
                       "directory".format(args.out))
        return 1

    # Load samples
    sample_lists = []
    sample_prefixes = []
    if args.samples:
        sfiles = args.samples.split(",")
        if args.sample_prefixes:
            sample_prefixes = args.sample_prefixes.split(",")
        else:
            sample_prefixes = [str(item) for item in range(1, len(sfiles)+1)]
        if len(sfiles) != len(sample_prefixes):
            common.MSG("--sample-prefixes must be same length as --samples")
            return 1
        for sf in sfiles:
            sample_lists.append([item.strip() for item in open(sf, "r").readlines()])

    checkgz = args.region is not None
    invcf = utils.LoadSingleReader(args.vcf, checkgz=checkgz)
    if invcf is None:
        return 1
    if args.vcftype != 'auto':
        vcftype = trh.VcfTypes[args.vcftype]
    else:
        vcftype = trh.InferVCFType(invcf)

    header = ["chrom","start","end"]
    if args.thresh: header.extend(GetHeader("thresh", sample_prefixes))
    if args.afreq: header.extend(GetHeader("afreq", sample_prefixes))
    if args.acount: header.extend(GetHeader("acount", sample_prefixes))
    if args.hwep: header.extend(GetHeader("hwep", sample_prefixes))
    if args.het: header.extend(GetHeader("het", sample_prefixes))
    if args.entropy: header.extend(GetHeader("entropy", sample_prefixes))
    if args.mean: header.extend(GetHeader("mean", sample_prefixes))
    if args.mode: header.extend(GetHeader("mode", sample_prefixes))
    if args.var: header.extend(GetHeader("var", sample_prefixes))
    if args.numcalled: header.extend(GetHeader("numcalled", sample_prefixes))

    precision_format = "\t{:." + str(args.precision) + "}"
    try:
        if args.out == "stdout":
            if args.plot_afreq:
                common.MSG("Cannot use --out stdout when generating plots")
                return 1
            outf = sys.stdout
        else:
            outf = open(args.out + ".tab", "w")
        outf.write("\t".join(header)+"\n")

        if args.region:
            region = invcf(args.region)
        else: region = invcf
        num_plotted = 0

        start_time = time.time()
        nrecords = 0
        for record in region:
            nrecords += 1

            trrecord = trh.HarmonizeRecord(vcftype, record)
            if args.plot_afreq and num_plotted <= MAXPLOTS:
                PlotAlleleFreqs(trrecord, args.out, samplelists=sample_lists, sampleprefixes=sample_prefixes)
                num_plotted += 1
            outf.write(str(record.CHROM) + "\t"
                       + str(record.POS) + "\t"
                       + str(record.POS+len(trrecord.ref_allele)))
            if args.thresh:
                for val in GetThresh(trrecord, samplelists=sample_lists):
                    outf.write(format_nan_precision(precision_format, val))
            if args.afreq:
                for val in GetAFreq(trrecord, samplelists=sample_lists,
                                    uselength=args.use_length):
                    outf.write("\t" + str(val))
            if args.acount:
                for val in GetAFreq(trrecord, samplelists=sample_lists,
                                    uselength=args.use_length, count=True):
                    outf.write("\t" + str(val))
            if args.hwep:
                for val in GetHWEP(trrecord, samplelists=sample_lists,
                                   uselength=args.use_length):
                    outf.write(format_nan_precision(precision_format, val))
            if args.het:
                for val in GetHet(trrecord, samplelists=sample_lists,
                                  uselength=args.use_length):
                    outf.write(format_nan_precision(precision_format, val))
            if args.entropy:
                for val in GetEntropy(trrecord, samplelists=sample_lists,
                                      uselength=args.use_length):
                    outf.write(format_nan_precision(precision_format, val))
            if args.mean:
                for val in GetMean(trrecord, samplelists=sample_lists):
                    outf.write(format_nan_precision(precision_format, val))
            if args.mode:
                for val in GetMode(trrecord, samplelists=sample_lists):
                    outf.write(format_nan_precision(precision_format, val))
            if args.var:
                for val in GetVariance(trrecord, samplelists=sample_lists):
                    outf.write(format_nan_precision(precision_format, val))
            if args.numcalled:
                for val in GetNumSamples(trrecord, samplelists=sample_lists):
                    outf.write("\t" + str(val))
            outf.write("\n")
            if nrecords % 50 == 0:
                outf.flush()
            if args.out != "stdout" and nrecords % 50 == 0:
                print(
                    "Finished {} records, time/record={:.5}sec".format(
                        nrecords, (time.time() - start_time)/nrecords
                    ),
                    flush=True,
                    end="\r"
                )
    finally:
        if outf is not None and args.out != "stdout":
            outf.close()

    if args.out != "stdout":
        print("\nDone", flush=True)

    return 0

def run(): # pragma: no cover
    args = getargs()
    if args == None:
        sys.exit(1)
    else:
        retcode = main(args)
        sys.exit(retcode)

if __name__ == "__main__": # pragma: no cover
    run()
