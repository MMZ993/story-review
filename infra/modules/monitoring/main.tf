# Cloud Monitoring slice (Phase 8 increment 6 slice C): log-based metrics
# over the orchestration service's structured application events
# (app_events.py), the two designed alert policies (observability.md
# "Alert policies cover retry exhaustion and delegation validation
# failure" — no notification channels yet, owner decision), and one
# dashboard combining request-level Cloud Run metrics with the
# application events.
terraform {
  required_version = ">= 1.16.0, < 2.0.0"
}

# ---- log-based metrics (delta counters on the application events) ----

resource "google_logging_metric" "retry_exhausted" {
  name    = "app-retry-exhausted"
  project = var.project_id
  filter  = "resource.type=\"cloud_run_revision\" AND jsonPayload.service=\"orchestration\" AND jsonPayload.event=\"retry_exhausted\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_logging_metric" "delegation_validation_failed" {
  name    = "app-delegation-validation-failed"
  project = var.project_id
  filter  = "resource.type=\"cloud_run_revision\" AND jsonPayload.service=\"orchestration\" AND jsonPayload.event=\"delegation_validation_failed\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_logging_metric" "gate_decisions" {
  name    = "app-gate-decisions"
  project = var.project_id
  filter  = "resource.type=\"cloud_run_revision\" AND jsonPayload.service=\"orchestration\" AND jsonPayload.event=\"gate_decision\""

  # One series per gate outcome (continue / finalize / park).
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"

    labels {
      key        = "outcome"
      value_type = "STRING"
    }
  }

  label_extractors = {
    outcome = "EXTRACT(jsonPayload.outcome)"
  }
}

resource "google_logging_metric" "sessions_parked" {
  name    = "app-sessions-parked"
  project = var.project_id
  filter  = "resource.type=\"cloud_run_revision\" AND jsonPayload.service=\"orchestration\" AND jsonPayload.event=\"session_parked\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

# ---- alert policies (observability.md's two designed alerts) ----
# No notification channels yet (owner decision 2026-09-16): the policies
# are visible/incident-creating in Cloud Monitoring only.

resource "google_monitoring_alert_policy" "retry_exhaustion" {
  project      = var.project_id
  display_name = "story-review: retry exhaustion"
  combiner     = "OR"

  # Any single occurrence in the window opens an incident: these events
  # already mean the shared client's full retry budget ran out.
  conditions {
    display_name = "any retry_exhausted application event"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/app-retry-exhausted\" AND resource.type=\"cloud_run_revision\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"

      trigger {
        count = 1
      }

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  alert_strategy {
    auto_close = "3600s"
  }
}

resource "google_monitoring_alert_policy" "delegation_validation" {
  project      = var.project_id
  display_name = "story-review: delegation-validation failure"
  combiner     = "OR"

  conditions {
    display_name = "any delegation_validation_failed application event"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/app-delegation-validation-failed\" AND resource.type=\"cloud_run_revision\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"

      trigger {
        count = 1
      }

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  alert_strategy {
    auto_close = "3600s"
  }
}

# ---- dashboard ----
# Provider 6.50 exposes only dashboard_json here, and the dashboards API
# it drives rejects `promqlQuery` fields ("Unknown name promqlQuery") —
# learned live at the slice-C apply; widgets therefore use classic
# timeSeriesFilter aggregations, XyChart tiles need at least 2x2 cells,
# and notification_rate_limit is log-based-policy-only.

resource "google_monitoring_dashboard" "story_review" {
  project = var.project_id

  dashboard_json = jsonencode({
    displayName = "story-review"
    mosaicLayout = {
      columns = 2
      tiles = [
        {
          xPos   = 0
          yPos   = 0
          width  = 2
          height = 2
          widget = {
            title = "Requests per second by service"
            xyChart = {
              dataSets = [{
                plotType = "LINE"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"run.googleapis.com/request_count\" AND resource.type=\"cloud_run_revision\""
                    aggregation = {
                      alignmentPeriod    = "300s"
                      perSeriesAligner   = "ALIGN_RATE"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields      = ["metric.label.\"service_name\""]
                    }
                  }
                }
              }]
            }
          }
        },
        {
          xPos   = 0
          yPos   = 2
          width  = 2
          height = 2
          widget = {
            title = "Request latency p95 (orchestration)"
            xyChart = {
              dataSets = [{
                plotType = "LINE"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"run.googleapis.com/http_server_request_latencies\" AND resource.type=\"cloud_run_revision\" AND metric.label.\"service_name\"=\"orchestration\""
                    aggregation = {
                      alignmentPeriod  = "300s"
                      perSeriesAligner = "ALIGN_PERCENTILE_95"
                    }
                  }
                }
              }]
            }
          }
        },
        {
          xPos   = 0
          yPos   = 4
          width  = 2
          height = 2
          widget = {
            title = "5xx response rate (orchestration)"
            xyChart = {
              dataSets = [{
                plotType = "LINE"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"run.googleapis.com/request_count\" AND resource.type=\"cloud_run_revision\" AND metric.label.\"service_name\"=\"orchestration\" AND metric.label.\"response_code_class\"=\"500\""
                    aggregation = {
                      alignmentPeriod    = "300s"
                      perSeriesAligner   = "ALIGN_RATE"
                      crossSeriesReducer = "REDUCE_SUM"
                    }
                  }
                }
              }]
            }
          }
        },
        {
          xPos   = 0
          yPos   = 6
          width  = 2
          height = 2
          widget = {
            title = "Application events (per second, 5m rate)"
            xyChart = {
              dataSets = [
                {
                  plotType = "STACKED_BAR"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/app-gate-decisions\" AND resource.type=\"cloud_run_revision\""
                      aggregation = {
                        alignmentPeriod    = "300s"
                        perSeriesAligner   = "ALIGN_RATE"
                        crossSeriesReducer = "REDUCE_SUM"
                        groupByFields      = ["metric.label.\"outcome\""]
                      }
                    }
                  }
                },
                {
                  plotType = "LINE"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/app-retry-exhausted\" AND resource.type=\"cloud_run_revision\""
                      aggregation = {
                        alignmentPeriod    = "300s"
                        perSeriesAligner   = "ALIGN_RATE"
                        crossSeriesReducer = "REDUCE_SUM"
                      }
                    }
                  }
                },
                {
                  plotType = "LINE"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/app-delegation-validation-failed\" AND resource.type=\"cloud_run_revision\""
                      aggregation = {
                        alignmentPeriod    = "300s"
                        perSeriesAligner   = "ALIGN_RATE"
                        crossSeriesReducer = "REDUCE_SUM"
                      }
                    }
                  }
                },
                {
                  plotType = "LINE"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/app-sessions-parked\" AND resource.type=\"cloud_run_revision\""
                      aggregation = {
                        alignmentPeriod    = "300s"
                        perSeriesAligner   = "ALIGN_RATE"
                        crossSeriesReducer = "REDUCE_SUM"
                      }
                    }
                  }
                }
              ]
            }
          }
        }
      ]
    }
  })
}
