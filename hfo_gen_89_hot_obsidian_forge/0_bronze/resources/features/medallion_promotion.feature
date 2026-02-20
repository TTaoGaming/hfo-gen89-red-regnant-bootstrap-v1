@infra @medallion @red
Feature: Medallion Promotion — Bronze to Silver Gate
  As an HFO operator
  I want a structural promotion gate from bronze to silver
  So that documents can advance (currently 9860 bronze, 0 promoted)

  Background:
    Given the SSOT database is connected

  Scenario: Promotion gate function exists
    Given the medallion promotion module is importable
    Then the promote_to_silver function is callable

  Scenario: Promotion requires minimum validation criteria
    Given a bronze document without validation metadata
    When I attempt to promote it to silver
    Then the promotion is rejected with reason "missing validation"

  Scenario: Promotion with valid criteria succeeds
    Given a bronze document with passing validation metadata
    When I promote it to silver
    Then the document medallion field is updated to "silver"
    And a promotion stigmergy event is logged

  Scenario: At least 1 document has been promoted to silver
    When I count documents with medallion "silver" or higher
    Then there is at least 1 promoted document
