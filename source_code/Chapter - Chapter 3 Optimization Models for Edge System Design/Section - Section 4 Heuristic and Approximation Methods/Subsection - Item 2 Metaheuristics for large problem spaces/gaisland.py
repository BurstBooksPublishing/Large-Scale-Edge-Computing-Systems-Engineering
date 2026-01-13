from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor, as_completed
import random, math, time, numpy as np
from typing import List, Tuple, Callable

@dataclass
class Individual:
    genes: np.ndarray  # assignment vector or encoding
    fitness: float = math.inf

def evaluate_fitness(genes: np.ndarray) -> float:
    # Placeholder: replace with ONNX/TF inference cost model or RPC to edge node
    latency = float(np.sum(genes * np.linspace(1.0, 2.0, genes.size)))
    energy = float(np.sum(genes * np.linspace(0.5, 1.5, genes.size)))
    return 0.7*latency + 0.3*energy

def tournament_select(pop: List[Individual], k: int=3) -> Individual:
    return min(random.sample(pop, k), key=lambda ind: ind.fitness)

def uniform_crossover(a: np.ndarray, b: np.ndarray, p: float=0.5) -> np.ndarray:
    mask = np.random.rand(a.size) < p
    child = np.where(mask, a, b)
    return child

def mutate(genes: np.ndarray, pm: float=0.01) -> np.ndarray:
    for i in range(genes.size):
        if random.random() < pm:
            genes[i] = 1 - genes[i]  # binary flip; adapt for real encoding
    return genes

def island_ga(pop_size: int, gene_len: int, gens: int,
              migrate_every: int, migrate_k: int,
              fitness_fn: Callable[[np.ndarray], float]):
    # initialize population
    pop = [Individual(genes=(np.random.rand(gene_len) > 0.5).astype(int)) for _ in range(pop_size)]
    # parallel fitness evaluation pool
    with ProcessPoolExecutor(max_workers=8) as pool:
        for ind in pop:
            ind.fitness = fitness_fn(ind.genes)
        for gen in range(gens):
            new_pop: List[Individual] = []
            # steady-state with elitism
            elite = min(pop, key=lambda x: x.fitness)
            new_pop.append(Individual(genes=elite.genes.copy(), fitness=elite.fitness))
            # generate offspring in parallel
            futures = []
            while len(new_pop) < pop_size:
                p1 = tournament_select(pop)
                p2 = tournament_select(pop)
                child_genes = uniform_crossover(p1.genes, p2.genes)
                child_genes = mutate(child_genes)
                futures.append(pool.submit(fitness_fn, child_genes))
                new_pop.append(Individual(genes=child_genes))
            # collect fitness results
            for ind, fut in zip(new_pop[1:], as_completed(futures)):
                ind.fitness = fut.result()
            pop = new_pop
            # migration hook (stub): send/receive elites with other islands
            if gen % migrate_every == 0 and gen > 0:
                # application should implement networked migration here
                pass
    return min(pop, key=lambda x: x.fitness)

# Example invocation (run on aggregation node)
if __name__ == "__main__":
    best = island_ga(pop_size=64, gene_len=500, gens=200,
                     migrate_every=20, migrate_k=2,
                     fitness_fn=evaluate_fitness)
    print("Best fitness:", best.fitness)