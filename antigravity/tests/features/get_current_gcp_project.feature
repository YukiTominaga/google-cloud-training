Feature: Get current GCP project
  As an AI assistant
  I want to retrieve the currently active GCP project ID
  So that I can safely interact with the intended GCP resources

  Scenario 1: Successfully retrieve the active GCP project
    Given gcloud CLI is installed
    And gcloud config has active project "my-sample-project"
    When get_current_gcp_project is called
    Then the result status should be "success"
    And the result project should be "my-sample-project"

  Scenario 2: Fail to retrieve GCP project when gcloud command fails
    Given gcloud CLI is installed
    And gcloud command fails with error "No project set"
    When get_current_gcp_project is called
    Then the result status should be "error"
    And the result error message should contain "No project set"

  Scenario 3: Fail to retrieve GCP project when gcloud is not installed
    Given gcloud CLI is not installed
    When get_current_gcp_project is called
    Then the result status should be "error"
    And the result error message should contain "not installed"

  Scenario 4: Fail to retrieve GCP project when command times out
    Given gcloud CLI is installed
    And gcloud command times out
    When get_current_gcp_project is called
    Then the result status should be "error"
    And the result error message should contain "timed out"

  Scenario 5: Fail to retrieve GCP project when gcloud returns "(unset)"
    Given gcloud CLI is installed
    And gcloud command succeeds with output "(unset)"
    When get_current_gcp_project is called
    Then the result status should be "error"
    And the result error message should contain "not set"

  Scenario 6: Fail to retrieve GCP project when gcloud returns an empty output
    Given gcloud CLI is installed
    And gcloud command succeeds with output ""
    When get_current_gcp_project is called
    Then the result status should be "error"
    And the result error message should contain "not set"

  Scenario 7: Invoke gcloud without a shell and with a timeout
    Given gcloud CLI is installed
    And gcloud config has active project "my-sample-project" and calls are recorded
    When get_current_gcp_project is called
    Then gcloud should have been invoked without a shell
    And gcloud should have been invoked with a finite timeout
