# torch-board

A lightweight dashboard for monitoring machine-learning training in real
time.

## Purpose

`torch-board` helps you observe what happens during model optimization
while training runs on a **remote machine** and the dashboard runs on
your **local machine**.

Train a model with a chosen architecture and dataset, watch its
statistics live, spot problems such as exploding gradients, `NaN`
values, or infinities, then adjust the architecture or training setup
and repeat.

The central idea is to keep training and telemetry production close to
the remote compute, while keeping visualization and interaction on the
local machine.

## High-level architecture

                                    Remote machine
                                    Model training
                                 Telemetry collection
                                          |
                                          | HTTP
                                          |
                                          ∨
                                     Local machine
                                       Backend
                          FastAPI • Validation • Chart preparation
                          |                                      |
                          |                                      |
                          |                                      |
                          ∨                                      ∨
                       Database                             Live Updates
                        SQLite                               WebSockets
                                                                 |
                                                                 |
                                                                 |
                                                                 ∨
                                                             Frontend
                                                         Dashboard • Charts

### Data flow

1.  A training process runs on a remote machine.
2.  A telemetry collector extracts training information.
3.  The remote machine sends telemetry to the local backend over HTTP.
4.  The backend validates and processes incoming data.
5.  The backend stores data in SQLite and publishes live updates over
    WebSockets.
6.  The local frontend displays the dashboard and charts.

## Telemetry collection

The project should support multiple ways of collecting training
information, ranging from lightweight integrations to richer data:

-   **stdout** - read statistics already printed by a
    training process.
-   **JSON telemetry** - send structured telemetry from the remote
    machine.
-   **Remote-produced histograms** - create histogram data on
    the remote machine, avoiding the need to transmit every underlying
    sample.

These are complementary collection paths. They should feed a common
backend pipeline so the dashboard does not need to know how each kind of
telemetry was produced.

## Technology stack

Backend: FastAPI, uvicorn   | HTTP API, validation, processing and chart-data preparation

Storage: SQLite             | Persist collected telemetry

Live updates: WebSockets    | Push new data to the dashboard

Frontend: React             | Dashboard

Charts: uPlot               | Render training statistics (claims to be the fastest)

## Project scope

The primary goal is live monitoring of training statistics, not
providing a model-training framework. The user remains responsible for
defining and running the training workload; `torch-board` collects and
presents its telemetry.

The exact telemetry fields, API endpoints, persistence model, dashboard
interactions and deployment approach will be defined as the
corresponding parts of the system are implemented.
