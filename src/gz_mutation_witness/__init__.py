"""Mutation-sweep witness with a four-way verdict: killed, survived, invalid, inconclusive."""

from gz_mutation_witness.witness import (
    Mutation,
    MutationOutcome,
    MutationSweep,
    MutationWitness,
    run_mutation_sweep,
)

__all__ = ["Mutation", "MutationOutcome", "MutationSweep", "MutationWitness", "run_mutation_sweep"]
