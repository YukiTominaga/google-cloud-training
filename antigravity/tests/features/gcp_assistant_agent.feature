Feature: GCP Assistant Agent
  As a Google Cloud developer
  I want a root AI assistant configured with safe GCP project inspection capabilities
  So that I can interactively inspect my Google Cloud environment securely

  Scenario 1: Verify root workflow agent configuration with default parameters
    Given the gcp_assistant agent module is loaded
    When root_agent is inspected
    Then the agent name should be "gcp_assistant"
    And the agent type should be "Workflow"
    And the workflow should contain node "gcp_assistant_node"
    And the node model should be "gemini-4-argon"
    And the node tools should contain "get_current_gcp_project"
    And the workflow edges should contain from "START" to "gcp_assistant_node"
    And the node instruction should require using "get_current_gcp_project" for project identification

  Scenario 2: Verify agent metadata via get_agent_info
    Given the gcp_assistant agent module is loaded
    When get_agent_info is called
    Then the result status should be "success"
    And the result agent name should be "gcp_assistant"
    And the result agent type should be "Workflow"
    And the result node name should be "gcp_assistant_node"
    And the result agent model should be "gemini-4-argon"
    And the result agent tools should contain "get_current_gcp_project"
    And the result edges should contain from "START" to "gcp_assistant_node"

  Scenario 3: Propagate tool failure when gcloud CLI is not installed
    Given gcloud CLI is not installed
    When the agent invokes get_current_gcp_project tool
    Then the tool result status should be "error"
    And the tool result error should contain "not installed"

  Scenario 4: Propagate tool failure when GCP project is unset
    Given gcloud CLI is installed
    And gcloud command succeeds with output "(unset)"
    When the agent invokes get_current_gcp_project tool
    Then the tool result status should be "error"
    And the tool result error should contain "not set"

  Scenario 5: Agent factory falls back to default model when model is empty
    Given a model name is specified as ""
    When create_gcp_assistant_agent is called with the model name
    Then the created agent type should be "Workflow"
    And the created agent name should be "gcp_assistant"
    And the created agent node model should be "gemini-4-argon"

  Scenario 6: Agent factory falls back to default model when model is whitespace
    Given a model name is specified as "   "
    When create_gcp_assistant_agent is called with the model name
    Then the created agent node model should be "gemini-4-argon"

  Scenario 7: Agent factory trims whitespace when model name has surrounding spaces
    Given a model name is specified as "  gemini-4-argon  "
    When create_gcp_assistant_agent is called with the model name
    Then the created agent type should be "Workflow"
    And the created agent name should be "gcp_assistant"
    And the created agent node model should be "gemini-4-argon"

  Scenario 8: Agent instruction enforces read-only operations and confidentiality
    Given the root_agent node instruction is inspected
    Then the instruction should require read-only operations
    And the instruction should prohibit modifying or deleting resources
    And the instruction should prohibit outputting tokens or private keys

  Scenario 9: Verify tool execution security with active project utaha-io
    Given gcloud CLI is installed
    And gcloud config has active project "utaha-io" and calls are recorded
    When the agent invokes get_current_gcp_project tool
    Then the tool result status should be "success"
    And the tool result project should be "utaha-io"
    And gcloud should have been invoked without a shell
    And gcloud should have been invoked with a finite timeout
