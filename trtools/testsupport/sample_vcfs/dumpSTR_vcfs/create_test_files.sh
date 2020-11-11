# Note: my directory structure is 
# trtools/
#  repo/ # trtools repo clone I'm developing in, on whatever the dev branch is
#  release/ # another trtools repo clone, with master branch checked out.
#           # I run the tests scripts to generate the test files from this directory

# Note: the thresholds in this file are arbitrary and just used for testing
# do not assume they are reasonable for data analysis

out=../repo/trtools/testsupport/sample_vcfs/dumpSTR_vcfs

# base_filters
python -m trtools.dumpSTR.dumpSTR --vcf example-files/trio_chr21_hipstr.sorted.vcf.gz --out $out/base_filters --min-locus-callrate 0.5 --min-locus-hwep 0.5 --min-locus-het 0.05 --max-locus-het 0.45 --filter-regions-names foo_region --filter-regions ../repo/trtools/testsupport/sample_vcfs/dumpSTR_vcfs/sample_region.bed.gz --vcftype hipstr

# base_filters_drop - only difference should be the vcf file, so delete the other two
python -m trtools.dumpSTR.dumpSTR --vcf example-files/trio_chr21_hipstr.sorted.vcf.gz --out $out/base_filters_drop --min-locus-callrate 0.5 --min-locus-hwep 0.5 --min-locus-het 0.05 --max-locus-het 0.45 --filter-regions-names foo_region --filter-regions ../repo/trtools/testsupport/sample_vcfs/dumpSTR_vcfs/sample_region.bed.gz --vcftype hipstr --drop-filtered
rm $out/base_filters_drop.samplog.tab
rm $out/base_filters_drop.loclog.tab

# advntr_filters
python -m trtools.dumpSTR.dumpSTR --vcf example-files/NA12878_chr21_advntr.sorted.vcf.gz --out $out/advntr_filters --advntr-min-call-DP 50 --advntr-max-call-DP 2000  --advntr-min-spanning 1 --advntr-min-flanking 20 --advntr-min-ML 0.95

# eh_filters
# TODO some of the EH filters never worked in the first place
# python -m trtools.dumpSTR.dumpSTR --vcf example-files/NA12878_chr21_eh.sorted.vcf.gz --out $out/eh_filters --eh-min-ADFL 3 --eh-min-ADIR 3 --eh-min-ADSP 1 --eh-min-call-LC 50 --eh-max-call-LC 1000

# gangstr_filters
python -m trtools.dumpSTR.dumpSTR --vcf trtools/testsupport/sample_vcfs/test_gangstr.vcf --out $out/gangstr_filters --gangstr-min-call-DP 10 --gangstr-max-call-DP 50 --gangstr-min-call-Q 0.9  --gangstr-filter-span-only --gangstr-filter-spanbound-only --gangstr-filter-badCI --gangstr-require-support 10 --gangstr-readlen 150 --gangstr-expansion-prob-het 0.001 --gangstr-expansion-prob-hom 0.0005 --gangstr-expansion-prob-total 0.001

# hipstr_filters
python -m trtools.dumpSTR.dumpSTR --vcf example-files/trio_chr21_hipstr.sorted.vcf.gz --out $out/hipstr_filters --filter-hrun --use-length --max-locus-het 0.45 --min-locus-het 0.05 --min-locus-hwep 0.5 --hipstr-max-call-flank-indel 0.05 --hipstr-max-call-stutter 0.3 --hipstr-min-supp-reads 10 --hipstr-min-call-DP 30 --hipstr-max-call-DP 200 --hipstr-min-call-Q 0.9 --vcftype hipstr

# popstr_filters
python -m trtools.dumpSTR.dumpSTR --vcf example-files/NA12878_chr21_popstr.sorted.vcf.gz --out $out/popstr_filters --popstr-min-call-DP 30 --popstr-max-call-DP 200 --popstr-require-support 15
