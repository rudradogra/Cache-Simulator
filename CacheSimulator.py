"""
Cache Simulator - L1 Data Cache Performance Analysis
Based on COA Lab Report specifications:
- Cache Size: 32 KB
- Block Size: 64 bytes
- Associativity: 4-way set associative
- Number of Sets: 128
- Replacement Policy: LRU
- Write Policy: Write-Back
- Allocation Policy: Write-Allocate
"""

import random
from collections import OrderedDict
from typing import Tuple, Dict, List

class CacheLine:
    """Represents a single cache line"""
    def __init__(self):
        self.valid = False
        self.dirty = False
        self.tag = None
        self.data = None  # Simulated data (not actually stored)

class CacheSet:
    """Represents a cache set with LRU replacement"""
    def __init__(self, associativity: int):
        self.associativity = associativity
        # OrderedDict maintains insertion order - most recent at end
        self.lines: OrderedDict[int, CacheLine] = OrderedDict()
    
    def find(self, tag: int) -> CacheLine:
        """Find a line with matching tag, update LRU order if found"""
        if tag in self.lines:
            # Move to end (most recently used)
            self.lines.move_to_end(tag)
            return self.lines[tag]
        return None
    
    def insert(self, tag: int) -> Tuple[bool, int]:
        """
        Insert a new line, evicting if necessary
        Returns: (was_dirty, evicted_tag) or (False, None) if no eviction
        """
        evicted_dirty = False
        evicted_tag = None
        
        # Check if we need to evict
        if len(self.lines) >= self.associativity:
            # Evict LRU (first item in OrderedDict)
            evicted_tag, evicted_line = self.lines.popitem(last=False)
            evicted_dirty = evicted_line.dirty
        
        # Insert new line
        new_line = CacheLine()
        new_line.valid = True
        new_line.tag = tag
        self.lines[tag] = new_line
        
        return evicted_dirty, evicted_tag
    
    def is_full(self) -> bool:
        return len(self.lines) >= self.associativity


class CacheSimulator:
    """L1 Data Cache Simulator"""
    
    def __init__(self, cache_size_kb=32, block_size=64, associativity=4, enable_prefetch=False):
        self.cache_size = cache_size_kb * 1024  # Convert to bytes
        self.block_size = block_size
        self.associativity = associativity
        self.enable_prefetch = enable_prefetch
        
        # Calculate derived values
        self.num_sets = self.cache_size // (block_size * associativity)
        self.offset_bits = self._log2(block_size)
        self.index_bits = self._log2(self.num_sets)
        
        # Initialize cache sets
        self.sets: List[CacheSet] = [CacheSet(associativity) for _ in range(self.num_sets)]
        
        # Statistics
        self.stats = {
            'total_accesses': 0,
            'hits': 0,
            'misses': 0,
            'compulsory_misses': 0,
            'conflict_misses': 0,
            'capacity_misses': 0,
            'reads': 0,
            'writes': 0,
            'memory_reads': 0,
            'memory_writes': 0,
            'prefetch_hits': 0,
            'prefetch_misses': 0
        }
        
        # Track all blocks ever accessed (for miss classification)
        self.accessed_blocks = set()
        # Track current blocks in cache (for capacity miss detection)
        self.blocks_in_cache = set()
        
        print(f"Cache Configuration:")
        print(f"  Cache Size: {cache_size_kb} KB")
        print(f"  Block Size: {block_size} bytes")
        print(f"  Associativity: {associativity}-way")
        print(f"  Number of Sets: {self.num_sets}")
        print(f"  Offset Bits: {self.offset_bits}")
        print(f"  Index Bits: {self.index_bits}")
        print(f"  Prefetching: {'Enabled' if enable_prefetch else 'Disabled'}")
        print()
    
    @staticmethod
    def _log2(n: int) -> int:
        """Calculate log base 2"""
        result = 0
        while n > 1:
            n >>= 1
            result += 1
        return result
    
    def _decompose_address(self, address: int) -> Tuple[int, int, int]:
        """
        Decompose address into tag, index, offset
        Returns: (tag, index, offset)
        """
        block_address = address >> self.offset_bits
        index = block_address & ((1 << self.index_bits) - 1)
        tag = block_address >> self.index_bits
        offset = address & ((1 << self.offset_bits) - 1)
        return tag, index, offset
    
    def _classify_miss(self, block_address: int, set_index: int) -> str:
        """Classify miss type: compulsory, conflict, or capacity"""
        if block_address not in self.accessed_blocks:
            return 'compulsory'
        
        # Check if cache is "full" (all sets have been used significantly)
        total_blocks_accessed = len(self.accessed_blocks)
        cache_capacity = self.num_sets * self.associativity
        
        if total_blocks_accessed > cache_capacity:
            # Could be capacity or conflict
            if self.sets[set_index].is_full():
                # Set is full - could be either
                if len(self.blocks_in_cache) >= cache_capacity:
                    return 'capacity'
                else:
                    return 'conflict'
            return 'capacity'
        else:
            return 'conflict'
    
    def access(self, address: int, is_write: bool = False, is_prefetch: bool = False) -> bool:
        """
        Access the cache
        Returns: True if hit, False if miss
        """
        tag, index, offset = self._decompose_address(address)
        block_address = address >> self.offset_bits
        cache_set = self.sets[index]
        
        # Update access statistics (not for prefetch)
        if not is_prefetch:
            self.stats['total_accesses'] += 1
            if is_write:
                self.stats['writes'] += 1
            else:
                self.stats['reads'] += 1
        
        # Check for hit
        line = cache_set.find(tag)
        
        if line is not None:
            # HIT
            if not is_prefetch:
                self.stats['hits'] += 1
            else:
                self.stats['prefetch_hits'] += 1
            
            if is_write:
                line.dirty = True  # Write-back policy
            
            return True
        
        # MISS
        if not is_prefetch:
            # Classify the miss
            miss_type = self._classify_miss(block_address, index)
            self.stats['misses'] += 1
            self.stats[f'{miss_type}_misses'] += 1
        else:
            self.stats['prefetch_misses'] += 1
        
        # Handle miss - evict and insert
        was_dirty, evicted_tag = cache_set.insert(tag)
        
        if was_dirty:
            self.stats['memory_writes'] += 1
            # Remove evicted block from tracking
            evicted_block = (evicted_tag << self.index_bits) | index
            self.blocks_in_cache.discard(evicted_block)
        
        # Fetch new block from memory
        self.stats['memory_reads'] += 1
        
        # Track accessed blocks
        self.accessed_blocks.add(block_address)
        self.blocks_in_cache.add(block_address)
        
        if is_write:
            cache_set.lines[tag].dirty = True
        
        # Optional next-line prefetch
        if self.enable_prefetch and not is_prefetch:
            next_address = address + self.block_size
            self.access(next_address, is_write=False, is_prefetch=True)
        
        return False
    
    def get_stats(self) -> Dict:
        """Get performance statistics"""
        total = self.stats['total_accesses']
        if total == 0:
            return self.stats
        
        stats = self.stats.copy()
        stats['hit_rate'] = (self.stats['hits'] / total) * 100
        stats['miss_rate'] = (self.stats['misses'] / total) * 100
        
        # Calculate AMAT (assuming L1 hit = 1 cycle, memory access = 100 cycles)
        l1_hit_time = 1
        memory_access_time = 100
        stats['amat'] = l1_hit_time + (stats['miss_rate'] / 100) * memory_access_time
        
        return stats
    
    def print_stats(self):
        """Print formatted statistics"""
        stats = self.get_stats()
        
        print("=" * 50)
        print("CACHE PERFORMANCE STATISTICS")
        print("=" * 50)
        print(f"Total Accesses:     {stats['total_accesses']:,}")
        print(f"  - Reads:          {stats['reads']:,}")
        print(f"  - Writes:         {stats['writes']:,}")
        print()
        print(f"Hits:               {stats['hits']:,}")
        print(f"Misses:             {stats['misses']:,}")
        print(f"  - Compulsory:     {stats['compulsory_misses']:,}")
        print(f"  - Conflict:       {stats['conflict_misses']:,}")
        print(f"  - Capacity:       {stats['capacity_misses']:,}")
        print()
        print(f"Hit Rate:           {stats.get('hit_rate', 0):.2f}%")
        print(f"Miss Rate:          {stats.get('miss_rate', 0):.2f}%")
        print()
        print(f"Memory Traffic:")
        print(f"  - Memory Reads:   {stats['memory_reads']:,}")
        print(f"  - Memory Writes:  {stats['memory_writes']:,}")
        print()
        if self.enable_prefetch:
            print(f"Prefetch Stats:")
            print(f"  - Prefetch Hits:  {stats['prefetch_hits']:,}")
            print(f"  - Prefetch Misses:{stats['prefetch_misses']:,}")
            print()
        print(f"AMAT (cycles):      {stats.get('amat', 0):.2f}")
        print("=" * 50)


def generate_sample_trace(num_accesses: int = 50000) -> List[Tuple[str, int]]:
    """
    Generate a sample memory access trace simulating a vision-based workload
    Returns list of (operation, address) tuples
    """
    trace = []
    
    # Simulate different memory regions
    frame_buffer_base = 0x11A3A000
    model_weights_base = 0x20893000
    inference_buffer_base = 0x21F9E000
    detection_list_base = 0x2123F000
    ui_buffer_base = 0x30ED0000
    
    regions = [
        ('LOAD', frame_buffer_base, 0x10000),      # Frame capture - sequential reads
        ('LOAD', model_weights_base, 0x50000),     # Model weights - large, reused
        ('LOAD', inference_buffer_base, 0x8000),   # Inference input
        ('STORE', detection_list_base, 0x2000),    # Detection results
        ('LOAD', ui_buffer_base, 0x4000),          # UI dimensions
    ]
    
    for _ in range(num_accesses):
        # Weighted selection to simulate realistic access patterns
        if random.random() < 0.4:
            # High locality access - repeated accesses to hot data
            op = 'LOAD'
            base = random.choice([frame_buffer_base, inference_buffer_base])
            offset = random.randint(0, 0x1000) & ~0x3F  # Align to 64 bytes
            addr = base + offset
        elif random.random() < 0.7:
            # Model weights - sequential with some reuse
            op = 'LOAD'
            addr = model_weights_base + (random.randint(0, 0x50000) & ~0x3F)
        else:
            # Random region access
            op, base, size = random.choice(regions)
            addr = base + (random.randint(0, size) & ~0x3F)
        
        trace.append((op, addr))
    
    return trace


def parse_trace_file(filename: str) -> List[Tuple[str, int]]:
    """
    Parse a trace file in format: timestamp,operation,address,object_name
    or simple format: operation address
    """
    trace = []
    
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split(',')
                if len(parts) >= 3:
                    # CSV format: timestamp,operation,address,...
                    op = parts[1].strip().upper()
                    addr_str = parts[2].strip()
                else:
                    # Simple format: operation address
                    parts = line.split()
                    if len(parts) >= 2:
                        op = parts[0].strip().upper()
                        addr_str = parts[1].strip()
                    else:
                        continue
                
                # Parse address (handle hex format)
                if addr_str.startswith('0x') or addr_str.startswith('0X'):
                    addr = int(addr_str, 16)
                else:
                    addr = int(addr_str)
                
                if op in ['LOAD', 'FETCH', 'READ']:
                    trace.append(('LOAD', addr))
                elif op in ['STORE', 'WRITE']:
                    trace.append(('STORE', addr))
    
    except FileNotFoundError:
        print(f"Trace file '{filename}' not found. Using generated trace.")
        return None
    
    return trace


def main():
    """Main function to run the cache simulation"""
    print("=" * 60)
    print("    PARA CACHE SIMULATOR - L1 Data Cache Analysis")
    print("=" * 60)
    print()
    
    # User choice for trace source
    print("Select trace source:")
    print("1. Use dummy/generated data (50,000 accesses)")
    print("2. Load from CSV file")
    print("3. Enter CSV filename manually")
    
    choice = input("\nEnter your choice (1/2/3) [default: 1]: ").strip()
    
    trace = None
    
    if choice == '2':
        # Try common filenames
        common_files = ['memory_trace.csv', 'trace.csv', 'cache_trace.csv']
        print("\nSearching for trace files...")
        
        for filename in common_files:
            import os
            if os.path.exists(filename):
                print(f"Found: {filename}")
                use_file = input(f"Use this file? (y/n) [y]: ").strip().lower()
                if use_file != 'n':
                    trace = parse_trace_file(filename)
                    if trace:
                        print(f"✓ Successfully loaded {len(trace)} accesses from {filename}\n")
                        break
        
        if trace is None:
            print("No trace files found. Using dummy data instead.\n")
    
    elif choice == '3':
        filename = input("Enter CSV filename: ").strip()
        trace = parse_trace_file(filename)
        if trace:
            print(f"✓ Successfully loaded {len(trace)} accesses from {filename}\n")
        else:
            print("Failed to load file. Using dummy data instead.\n")
    
    # Default to generated trace
    if trace is None:
        print("Generating sample memory access trace (50,000 accesses)...")
        trace = generate_sample_trace(50000)
        print(f"Generated {len(trace)} memory accesses\n")
    
    # Ask about number of accesses to simulate
    if len(trace) > 10000:
        use_all = input(f"Use all {len(trace):,} accesses? (y/n) [y]: ").strip().lower()
        if use_all == 'n':
            try:
                num_accesses = int(input(f"Enter number of accesses (1-{len(trace)}): "))
                trace = trace[:num_accesses]
                print(f"Using first {len(trace):,} accesses\n")
            except ValueError:
                print("Invalid input. Using all accesses.\n")
    
    # Run simulation without prefetching
    print("-" * 60)
    print("SIMULATION 1: Without Prefetching")
    print("-" * 60)
    
    cache = CacheSimulator(
        cache_size_kb=32,
        block_size=64,
        associativity=4,
        enable_prefetch=False
    )
    
    for op, addr in trace:
        is_write = (op == 'STORE')
        cache.access(addr, is_write=is_write)
    
    cache.print_stats()
    
    # Ask if user wants to run more simulations
    run_prefetch = input("\nRun simulation with prefetching? (y/n) [y]: ").strip().lower()
    
    if run_prefetch != 'n':
        # Run simulation with prefetching
        print("\n")
        print("-" * 60)
        print("SIMULATION 2: With Next-Line Prefetching")
        print("-" * 60)
        
        cache_prefetch = CacheSimulator(
            cache_size_kb=32,
            block_size=64,
            associativity=4,
            enable_prefetch=True
        )
        
        for op, addr in trace:
            is_write = (op == 'STORE')
            cache_prefetch.access(addr, is_write=is_write)
        
        cache_prefetch.print_stats()
    
    # Ask about configuration comparison
    run_comparison = input("\nRun configuration comparison? (y/n) [y]: ").strip().lower()
    
    if run_comparison != 'n':
        # Compare different cache configurations
        print("\n")
        print("=" * 60)
        print("CONFIGURATION COMPARISON")
        print("=" * 60)
    
    configs = [
        ("Direct Mapped (32KB)", 32, 64, 1),
        ("2-Way (32KB)", 32, 64, 2),
        ("4-Way (32KB)", 32, 64, 4),
        ("8-Way (32KB)", 32, 64, 8),
        ("4-Way (64KB)", 64, 64, 4),
    ]
    
    print(f"{'Configuration':<25} {'Hit Rate':>10} {'Miss Rate':>10} {'AMAT':>10}")
    print("-" * 60)
    
    for name, size, block, assoc in configs:
        # Create cache silently
        cache = CacheSimulator.__new__(CacheSimulator)
        cache.cache_size = size * 1024
        cache.block_size = block
        cache.associativity = assoc
        cache.enable_prefetch = False
        cache.num_sets = cache.cache_size // (block * assoc)
        cache.offset_bits = cache._log2(block)
        cache.index_bits = cache._log2(cache.num_sets)
        cache.sets = [CacheSet(assoc) for _ in range(cache.num_sets)]
        cache.stats = {
            'total_accesses': 0, 'hits': 0, 'misses': 0,
            'compulsory_misses': 0, 'conflict_misses': 0, 'capacity_misses': 0,
            'reads': 0, 'writes': 0, 'memory_reads': 0, 'memory_writes': 0,
            'prefetch_hits': 0, 'prefetch_misses': 0
        }
        cache.accessed_blocks = set()
        cache.blocks_in_cache = set()
        
        for op, addr in trace:
            cache.access(addr, is_write=(op == 'STORE'))
        
            stats = cache.get_stats()
            print(f"{name:<25} {stats.get('hit_rate', 0):>9.2f}% {stats.get('miss_rate', 0):>9.2f}% {stats.get('amat', 0):>9.2f}")
    
    # Save results option
    save_results = input("\nSave results to file? (y/n) [n]: ").strip().lower()
    if save_results == 'y':
        output_file = input("Enter output filename [cache_results.txt]: ").strip()
        if not output_file:
            output_file = "cache_results.txt"
        
        try:
            import sys
            original_stdout = sys.stdout
            with open(output_file, 'w') as f:
                sys.stdout = f
                print("=" * 60)
                print("CACHE SIMULATION RESULTS")
                print("=" * 60)
                print(f"Trace source: {len(trace):,} memory accesses")
                print()
                cache.print_stats()
            sys.stdout = original_stdout
            print(f"✓ Results saved to {output_file}")
        except Exception as e:
            print(f"Error saving file: {e}")
    
    print("\n" + "=" * 60)
    print("Simulation complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()