Feature: Get current GCP project
  As an AI assistant
  I want to retrieve the currently active GCP project ID
  So that I can safely interact with the intended GCP resources

  Scenario: Successfully retrieve the active GCP project
    Given gcloud CLI is installed
    And gcloud config has active project "my-sample-project"
    When get_current_gcp_project is called
    Then the result status should be "success"
    And the result project should be "my-sample-project"

  Scenario: Fail to retrieve GCP project when gcloud command fails
    Given gcloud CLI is installed
    And gcloud command fails with error "No project set"
    When get_current_gcp_project is called
    Then the result status should be "error"
    And the result error message should contain "No project set"

  Scenario: Fail to retrieve GCP project when gcloud is not installed
    Given gcloud CLI is not installed
    When get_current_gcp_project is called
    Then the result status should be "error"
    And the result error message should contain "not installed"

  Scenario: Fail to retrieve GCP project when command times out
    Given gcloud CLI is installed
    And gcloud command times out
    When get_current_gcp_project is called
    Then the result status should be "error"
    And the result error message should contain "timed out"
