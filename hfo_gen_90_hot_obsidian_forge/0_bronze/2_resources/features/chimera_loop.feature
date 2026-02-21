@p2 @chimera @red
Feature: P2 Chimera Loop — Evolutionary DSE SSOT Integration
  As the P2 Mirror Magus commander
  I want the chimera loop's evolutionary persona DSE to persist results to SSOT
  So that chimera deaths strengthen the swarm through stigmergy blood trails

  Background:
    Given the SSOT database is connected
    And the chimera loop module is importable

  Scenario: Genome random generation produces valid traits
    When I generate a random genome
    Then all 8 trait keys are present
    And every trait value is a valid allele for its key

  Scenario: Genome mutation preserves trait key structure
    Given a random genome
    When I mutate it with rate 0.5
    Then the mutated genome has the same 8 trait keys
    And at least 1 trait differs from the original

  Scenario: Genome crossover produces child with parent alleles only
    Given two random parent genomes
    When I crossover the parents
    Then the child has exactly 8 traits
    And every child allele comes from one of the two parents

  Scenario: Genome to_system_prompt renders all trait sections
    Given the default Red Regnant genome
    When I render it to a system prompt
    Then the prompt contains at least 200 characters
    And the prompt contains all 8 trait section markers

  Scenario: FitnessVector Pareto dominance is correct
    Given fitness vector A with all scores 0.8
    And fitness vector B with all scores 0.5
    Then A dominates B
    And B does not dominate A

  Scenario: FitnessVector aggregate uses correct weights
    Given fitness vector with coding_accuracy 1.0 and all others 0.0
    Then the aggregate score equals 0.30

  Scenario: SSOT has chimera stigmergy events after a loop run
    Given the SSOT database is connected
    When I count chimera stigmergy events
    Then there are at least 1 chimera events in SSOT

  Scenario: Chimera blood trail records genome traits and fitness
    Given the SSOT database is connected
    When I read the latest chimera eval event
    Then the event data contains genome_id
    And the event data contains traits dict
    And the event data contains aggregate_score
