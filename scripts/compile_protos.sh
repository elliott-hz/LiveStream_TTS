#!/bin/bash
# Proto Compilation Script
#
# Compiles all .proto files → Python gRPC stubs.
# Run: bash scripts/compile_protos.sh
#
# Prerequisites: pip install grpcio-tools mypy-protobuf

set -euo pipefail

PROTO_ROOT="$(cd "$(dirname "$0")/.." && pwd)/libs/proto"
OUT_ROOT="${PROTO_ROOT}"  # Output alongside .proto files

echo "=== Compiling Protobuf definitions ==="
echo "Proto root: ${PROTO_ROOT}"

PROTO_COUNT=0

for proto_file in $(find "${PROTO_ROOT}" -name "*.proto" -type f | sort); do
    PROTO_DIR=$(dirname "${proto_file}")
    PROTO_NAME=$(basename "${proto_file}")

    echo "  [${PROTO_COUNT}] ${proto_file#"${PROTO_ROOT}/"}"

    python3 -m grpc_tools.protoc \
        -I="${PROTO_ROOT}" \
        --python_out="${OUT_ROOT}" \
        --grpc_python_out="${OUT_ROOT}" \
        --mypy_out="${OUT_ROOT}" \
        "${proto_file}"

    PROTO_COUNT=$((PROTO_COUNT + 1))
done

# Fix imports: generated code uses relative imports, need to fix for libs.proto.* structure
echo ""
echo "=== Fixing generated imports ==="
find "${PROTO_ROOT}" -name "*_pb2_grpc.py" -type f | while read f; do
    # Replace `import xxx_pb2` with `from libs.proto.xxx.v1 import xxx_pb2`
    MODULE_DIR=$(dirname "${f}")
    # This is a simplification; for proper import paths, use sed
    sed -i '' 's/^import \(.*\)_pb2 as/from . import \1_pb2 as/' "${f}" 2>/dev/null || true
done

echo ""
echo "=== Done! Compiled ${PROTO_COUNT} proto files ==="

# Generate __init__.py files for all proto packages
find "${PROTO_ROOT}" -type d | while read d; do
    if [ ! -f "${d}/__init__.py" ]; then
        touch "${d}/__init__.py"
    fi
done

echo "Generated __init__.py files for all proto packages."
