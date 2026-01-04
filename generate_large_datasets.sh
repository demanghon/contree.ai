#!/bin/bash
set -e

# ==============================================================================
#  Coinche Dataset Generation Script (Large Server)
# ==============================================================================
#  Generates Bidding and Gameplay datasets with PIMC 1 and PIMC 50.
#  Runs sequentially to maximize CPU usage per task.
# ==============================================================================

# Configuration
# --------------------
BIDDING_SAMPLES=300000
GAMEPLAY_SAMPLES=1000000

# Directory for outputs
DIST_DIR="dist/datasets"
mkdir -p $DIST_DIR

# Script Path
SCRIPT="apps/coinche-dataset-generator/generate_datasets.py"
SCRIPT_DIR="apps/coinche-dataset-generator"

# Transposition Table Size
# 24 -> 256MB per thread. For 64 threads -> 16GB RAM.
# If OOM, reduce to 22 (64MB) or 20 (16MB).
TT_LOG2=24 

echo "========================================================"
echo "  Starting Dataset Generation"
echo "  Bidding Samples:  $BIDDING_SAMPLES"
echo "  Gameplay Samples: $GAMEPLAY_SAMPLES"
echo "  TT Log2 Size:     $TT_LOG2"
echo "========================================================"

# Remove cd $SCRIPT_DIR command as we run from root
# cd $SCRIPT_DIR || { echo "❌ Could not change directory to $SCRIPT_DIR"; exit 1; }

# Function to run generation
run_generation() {
    TYPE=$1
    SAMPLES=$2
    PIMC=$3
    OUTPUT_NAME=$4
    
    echo ""
    echo "--------------------------------------------------------"
    echo "🚀 Generating $TYPE (PIMC=$PIMC, N=$SAMPLES)"
    echo "   Output: $OUTPUT_NAME"
    echo "--------------------------------------------------------"
    
    start_time=$(date +%s)
    
    if [ "$TYPE" == "bidding" ]; then
        # Bidding output is a DIRECTORY (partitioned parquet)
        # We append the PIMC suffix to the base directory
        OUT_PATH="$DIST_DIR/$OUTPUT_NAME"
        
        python3 $SCRIPT \
            --bidding-samples $SAMPLES \
            --gameplay-samples 0 \
            --bidding-output "$OUT_PATH" \
            --pimc $PIMC \
            --tt-log2 $TT_LOG2 \
            --batch-size 1000 \
            --threads 0 # 0 = All Cores
            
    elif [ "$TYPE" == "gameplay" ]; then
        # Gameplay output is a FILE
        OUT_PATH="$DIST_DIR/$OUTPUT_NAME"
        
        python3 $SCRIPT \
            --bidding-samples 0 \
            --gameplay-samples $SAMPLES \
            --gameplay-output "$OUT_PATH" \
            --pimc $PIMC \
            --tt-log2 $TT_LOG2 \
            --batch-size 10000 \
            --threads 0
    fi
    
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    echo "✅ Completed $TYPE (PIMC=$PIMC) in ${duration}s"
}

# 1. Bidding (PIMC 1)
run_generation "bidding" $BIDDING_SAMPLES 1 "bidding_pimc1_300k"

# 2. Gameplay (PIMC 1)
run_generation "gameplay" $GAMEPLAY_SAMPLES 1 "gameplay_pimc1_1m.parquet"

# 3. Bidding (PIMC 50)
run_generation "bidding" $BIDDING_SAMPLES 50 "bidding_pimc50_300k"

# 4. Gameplay (PIMC 50)
run_generation "gameplay" $GAMEPLAY_SAMPLES 50 "gameplay_pimc50_1m.parquet"

echo ""
echo "========================================================"
echo "🎉 All Datasets Generated Successfully!"
echo "========================================================"
ls -lh $DIST_DIR
