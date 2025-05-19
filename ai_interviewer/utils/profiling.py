"""
Profiling utilities for performance optimization.

This module provides tools for measuring execution time and identifying
performance bottlenecks in the AI Interviewer system.
"""
import time
import logging
import functools
import cProfile
import io
import pstats
from typing import Optional, Callable, Any, Dict, List, Union
from contextlib import contextmanager

# Configure logging
logger = logging.getLogger(__name__)

@contextmanager
def timer(name: str, log_level: int = logging.DEBUG):
    """
    Context manager for timing code blocks.
    
    Args:
        name: Name of the operation being timed
        log_level: Logging level to use (default: DEBUG)
    
    Example:
        with timer("load_data"):
            data = load_large_dataset()
    """
    start_time = time.perf_counter()
    yield
    elapsed_time = time.perf_counter() - start_time
    logger.log(log_level, f"TIMER - {name}: {elapsed_time:.4f} seconds")

def timed_function(log_level: int = logging.INFO):
    """
    Decorator that logs the execution time of a function.
    
    Args:
        log_level: Logging level to use (default: INFO)
    
    Example:
        @timed_function()
        def slow_operation():
            # ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed_time = time.perf_counter() - start_time
            logger.log(log_level, f"TIMER - {func.__name__}: {elapsed_time:.4f} seconds")
            return result
        return wrapper
    return decorator

def profile_function(output_file: Optional[str] = None, sort_by: str = 'cumulative'):
    """
    Decorator that profiles a function using cProfile.
    
    Args:
        output_file: Optional file path to save profile results
        sort_by: Statistic by which to sort the profile results
                 (default: 'cumulative')
    
    Example:
        @profile_function(output_file="profile_results.txt")
        def complex_operation():
            # ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            profiler = cProfile.Profile()
            profiler.enable()
            
            result = func(*args, **kwargs)
            
            profiler.disable()
            
            # Process the stats
            s = io.StringIO()
            ps = pstats.Stats(profiler, stream=s).sort_stats(sort_by)
            ps.print_stats(20)  # Print top 20 results
            
            # Log the profile results
            logger.info(f"Profile results for {func.__name__}:\n{s.getvalue()}")
            
            # Save to file if requested
            if output_file:
                ps.dump_stats(output_file)
                logger.info(f"Profile results saved to {output_file}")
                
            return result
        return wrapper
    return decorator

class LangGraphProfiler:
    """
    Profiler specifically designed for measuring LangGraph performance.
    
    This class helps track execution times of different graph nodes and
    transitions to identify bottlenecks in the LangGraph workflow.
    """
    
    def __init__(self, graph_name: str = "default_graph"):
        """
        Initialize the LangGraph profiler.
        
        Args:
            graph_name: Name of the graph being profiled
        """
        self.graph_name = graph_name
        self.node_timings: Dict[str, List[float]] = {}
        self.transition_timings: Dict[str, List[float]] = {}
        self.current_operation: Optional[str] = None
        self.start_time: Optional[float] = None
        
    def start_node(self, node_name: str):
        """Record the start time of a node execution."""
        self.current_operation = f"node:{node_name}"
        self.start_time = time.perf_counter()
        
    def end_node(self, node_name: str):
        """Record the end time of a node execution."""
        if self.start_time is None or self.current_operation != f"node:{node_name}":
            logger.warning(f"Mismatched node timing for {node_name}")
            return
            
        elapsed = time.perf_counter() - self.start_time
        if node_name not in self.node_timings:
            self.node_timings[node_name] = []
            
        self.node_timings[node_name].append(elapsed)
        logger.info(f"GRAPH TIMING - Node {node_name}: {elapsed:.4f} seconds")
        
        self.current_operation = None
        self.start_time = None
        
    def start_transition(self, from_node: str, to_node: str):
        """Record the start time of a transition between nodes."""
        self.current_operation = f"transition:{from_node}->{to_node}"
        self.start_time = time.perf_counter()
        
    def end_transition(self, from_node: str, to_node: str):
        """Record the end time of a transition between nodes."""
        if self.start_time is None or self.current_operation != f"transition:{from_node}->{to_node}":
            logger.warning(f"Mismatched transition timing for {from_node}->{to_node}")
            return
            
        elapsed = time.perf_counter() - self.start_time
        transition_key = f"{from_node}->{to_node}"
        
        if transition_key not in self.transition_timings:
            self.transition_timings[transition_key] = []
            
        self.transition_timings[transition_key].append(elapsed)
        logger.info(f"GRAPH TIMING - Transition {transition_key}: {elapsed:.4f} seconds")
        
        self.current_operation = None
        self.start_time = None
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all timings collected."""
        node_summary = {}
        for node, times in self.node_timings.items():
            node_summary[node] = {
                "count": len(times),
                "total": sum(times),
                "average": sum(times) / len(times) if times else 0,
                "min": min(times) if times else 0,
                "max": max(times) if times else 0
            }
            
        transition_summary = {}
        for trans, times in self.transition_timings.items():
            transition_summary[trans] = {
                "count": len(times),
                "total": sum(times),
                "average": sum(times) / len(times) if times else 0,
                "min": min(times) if times else 0,
                "max": max(times) if times else 0
            }
            
        return {
            "graph_name": self.graph_name,
            "nodes": node_summary,
            "transitions": transition_summary,
            "total_node_time": sum(sum(times) for times in self.node_timings.values()),
            "total_transition_time": sum(sum(times) for times in self.transition_timings.values())
        }
    
    def print_summary(self):
        """Print a summary of timings to the log."""
        summary = self.get_summary()
        
        logger.info(f"\n----- LangGraph Profiler Summary for {self.graph_name} -----")
        
        # Sort nodes by total time (descending)
        sorted_nodes = sorted(
            summary["nodes"].items(), 
            key=lambda x: x[1]["total"], 
            reverse=True
        )
        
        logger.info("\nNode Timings (sorted by total time):")
        for node, stats in sorted_nodes:
            logger.info(f"  {node}:")
            logger.info(f"    Count: {stats['count']}")
            logger.info(f"    Total: {stats['total']:.4f} seconds")
            logger.info(f"    Average: {stats['average']:.4f} seconds")
            logger.info(f"    Min: {stats['min']:.4f} seconds")
            logger.info(f"    Max: {stats['max']:.4f} seconds")
        
        # Sort transitions by total time (descending)
        sorted_transitions = sorted(
            summary["transitions"].items(), 
            key=lambda x: x[1]["total"], 
            reverse=True
        )
        
        logger.info("\nTransition Timings (sorted by total time):")
        for trans, stats in sorted_transitions:
            logger.info(f"  {trans}:")
            logger.info(f"    Count: {stats['count']}")
            logger.info(f"    Total: {stats['total']:.4f} seconds")
            logger.info(f"    Average: {stats['average']:.4f} seconds")
            logger.info(f"    Min: {stats['min']:.4f} seconds")
            logger.info(f"    Max: {stats['max']:.4f} seconds")
        
        logger.info(f"\nTotal node time: {summary['total_node_time']:.4f} seconds")
        logger.info(f"Total transition time: {summary['total_transition_time']:.4f} seconds")
        logger.info("----- End of Summary -----\n") 