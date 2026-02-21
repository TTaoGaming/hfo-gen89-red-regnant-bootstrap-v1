Feature: Omega v14 Microkernel
  As a system architect
  I want a strict microkernel architecture
  So that plugins can be loaded and managed without modifying the core monolith

  Scenario: Registering a valid plugin
    Given the microkernel is initialized
    When a plugin with a valid manifest is registered
    Then the plugin should be added to the registry
    And the plugin's init method should be called

  Scenario: Registering an invalid plugin
    Given the microkernel is initialized
    When a plugin without a manifest is registered
    Then an error should be thrown
    And the plugin should not be added to the registry

  Scenario: Starting the microkernel
    Given the microkernel is initialized with registered plugins
    When the microkernel is started
    Then all registered plugins should have their start method called
    And the microkernel state should be "RUNNING"
