@infra @lineage @red
Feature: Lineage Tracking — Automatic Dependency Graph Population
  As an HFO operator
  I want the lineage table to be auto-populated from PREY8 memory_refs
  So that document dependency graphs exist (currently 0 rows)

  Background:
    Given the SSOT database is connected

  Scenario: Lineage table has rows
    When I count lineage table rows
    Then there are at least 10 lineage entries

  Scenario: Lineage entries link documents via memory_refs
    When I query lineage entries
    Then each entry has a source_doc_id and target_doc_id
    And both IDs exist in the documents table

  Scenario: Lineage auto-population from perceive memory_refs
    Given a perceive event with memory_refs "423,287,7855"
    When I run the lineage auto-populator
    Then lineage entries are created linking those documents
    And the lineage_type is "prey8_memory_ref"

  Scenario: Duplicate lineage entries are prevented
    Given existing lineage entries for docs 423 and 287
    When I run the lineage auto-populator again for the same refs
    Then no duplicate entries are created
