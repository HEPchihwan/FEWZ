SRC="/data6/Users/snuintern1/FEWZ/condor/FEWZ_3.1.rc/bin/0520_test_DY_NNLO/0520_test_DY_NNLO0/wrapper.sh"
DEST_BASE="/data6/Users/snuintern1/FEWZ/condor/FEWZ_3.1.rc/bin/0520_test_DY_NNLO"

for i in {1..126}; do
    dest_dir="${DEST_BASE}/0520_test_DY_NNLO${i}"
    if [ -d "$dest_dir" ]; then
        cp "$SRC" "$dest_dir/wrapper.sh"
        echo "Copied to $dest_dir"
    else
        echo "Directory $dest_dir not found!"
    fi
done