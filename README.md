# RISC-V CPU Simulator

A high-performance RISC-V CPU simulator implementing **Tomasulo's Algorithm** for out-of-order execution, built with the [Assassyn](https://github.com/assassyn-public/assassyn) hardware description framework.

## Contributors

- **Granthy** -  Optimization, predictor and debugging. Complete Div, Rem command for bonus.
- **Vitalrubbish** - Main architecture and testing. Complete Mul command for bonus.

## Features

### Architecture
- **Tomasulo's Algorithm**: Out-of-order execution with register renaming
- **Reorder Buffer (ROB)**: In-order commit for precise exceptions
- **Reservation Stations (RS)**: Dynamic instruction scheduling
- **Load/Store Queue (LSQ)**: Memory operation ordering
- **Branch Prediction**: 2-bit saturating counter with Branch Target Buffer (BTB)

### Supported Instructions (RV32IM)

#### RV32I Base Integer Instructions
| Category | Instructions |
|----------|-------------|
| Arithmetic | `add`, `sub`, `addi` |
| Logical | `and`, `or`, `xor`, `ori` |
| Shift | `sll`, `srl`, `sra` |
| Compare | `slt`, `sltu` |
| Branch | `beq`, `bne`, `blt`, `bge`, `bltu`, `bgeu` |
| Jump | `jal`, `jalr` |
| Load/Store | `lw`, `sw`, `lbu` |
| Upper Immediate | `lui` |
| System | `ebreak` |

#### RV32M Multiply/Divide Extension
| Category | Instructions | Description |
|----------|-------------|-------------|
| Multiply | `mul` | Multiply, return lower 32 bits |
| Multiply | `mulh` | Multiply signed×signed, return upper 32 bits |
| Multiply | `mulhu` | Multiply unsigned×unsigned, return upper 32 bits |
| Multiply | `mulhsu` | Multiply signed×unsigned, return upper 32 bits |
| Divide | `div` | Signed division |
| Divide | `divu` | Unsigned division |
| Remainder | `rem` | Signed remainder |
| Remainder | `remu` | Unsigned remainder |

### Hardware Units

- **ALU**: Basic arithmetic and logical operations (single-cycle)
- **MUL_ALU**: Pipelined multiplier with 3-stage pipeline
- **DIV_ALU**: Pipelined divider with 4-stage restoring division algorithm
- **Instruction Cache (icache)**: SRAM-based instruction memory
- **Data Cache (dcache)**: SRAM-based data memory

## Project Structure

```
RISC-V-CPU/
├── src/
│   ├── main.py           # Top-level CPU builder and simulation entry
│   ├── instruction.py    # Instruction definitions and encoding
│   ├── decode_logic.py   # Instruction decoder logic
│   ├── decoder.py        # Decoder module
│   ├── fetcher.py        # Instruction fetch unit
│   ├── ROB.py            # Reorder Buffer implementation
│   ├── RS.py             # Reservation Stations
│   ├── alu.py            # Arithmetic Logic Unit
│   ├── mul_alu.py        # Pipelined Multiplier
│   ├── div_alu.py        # Pipelined Divider
│   ├── lsq.py            # Load/Store Queue
│   ├── opcodes.py        # Opcode definitions
│   ├── utils.py          # Utility functions
│   └── workloads/        # Test programs and benchmarks
├── docs/
│   └── Arch.md           # Architecture documentation
└── README.md
```

## Prerequisites

- Docker
- Assassyn framework (included in Docker image)
- Verilator (for Verilog simulation)

## Quick Start with Docker

### 1. Pull and Run Docker Container

```bash
# Navigate to the Assassyn directory
cd /path/to/assassyn

# Run the Docker container with the project mounted
docker run --rm -it \
  -v "$(pwd):/app" \
  --user root \
  -m 32g \
  --name assassyn \
  assassyn:latest
```

### 2. Navigate to Project Directory

```bash
cd /app/RISC-V-CPU/src
```

### 3. Run Simulation

```bash
python main.py
```

This will:
1. Initialize the workspace with the selected workload
2. Build the Tomasulo CPU architecture
3. Generate Verilog code via Assassyn
4. Run Verilator simulation

### 4. Select Different Workloads

Edit `main.py` to change the workload:

```python
def build_cpu(depth_log: int):
    # Change "0to100" to any available workload
    init_workspace(f"{current_path}/workloads", "0to100")
    # ...
```

Available workloads include:
- `0to100` - Sum from 0 to 100
- `gcd` - Greatest Common Divisor
- `qsort` - Quick Sort
- `multiply` - Multiplication test
- `vector_add` - Vector addition
- `vector_multiply` - Vector multiplication
- And many more in `src/workloads/`

## Configuration

### Memory Configuration

The CPU uses configurable SRAM for instruction and data caches:

```python
depth_log = 16  # 2^16 = 65536 words of memory
```

### Branch Prediction

```python
BHT_LOG_SIZE = 6  # 2^6 = 64 entries in Branch History Table
```

### ROB/RS Size

In `ROB.py` and `RS.py`:
```python
ROB_SIZE = 8  # Reorder Buffer entries
RS_SIZE = 8   # Reservation Station entries
```

## Architecture Details

### Tomasulo Algorithm Implementation

1. **Issue**: Instructions are fetched and decoded, then dispatched to reservation stations
2. **Execute**: When operands are ready, instructions execute in functional units
3. **Write Result**: Results are broadcast via Common Data Bus (CDB)
4. **Commit**: ROB commits instructions in program order

### Pipeline Stages

```
Fetch → Decode → Issue → Execute → Write Back → Commit
                   ↓
            Reservation Stations
                   ↓
         ALU / MUL_ALU / DIV_ALU / LSQ
```

### Division Algorithm

The `DIV_ALU` implements a 4-stage pipelined restoring division:
- **Stage 1**: Sign handling and operand preparation
- **Stage 2**: Division iterations (bits 31-16)
- **Stage 3**: Division iterations (bits 15-0)
- **Stage 4**: Sign correction and result selection

## Creating Test Programs

Test programs are compiled using RISC-V GCC toolchain. Each workload requires:
- `.exe` - Binary executable (instruction memory)
- `.data` - Data section (data memory)
- `.config` - Memory offset configuration

Example config format:
```
offset: 0x0 data_offset: 0x10000
```

## Simulation Output

The simulation generates:
- Verilog RTL in `.workspace/`
- Verilator compilation logs
- Execution traces (when logging enabled)

## License

This project is developed as part of computer architecture coursework.

## Acknowledgments

- [Assassyn Framework](https://github.com/Synthesys-Lab/assassyn) - Hardware description and simulation
- RISC-V Foundation - ISA specification
