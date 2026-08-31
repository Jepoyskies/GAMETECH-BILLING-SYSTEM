# GM Dashboard & Monitoring Specification (Old sheet based)

## Dashboard Tab

### Summary Cards

| Metric                       | Formula                                                            |
| ---------------------------- | ------------------------------------------------------------------ |
| Installs (Total)             | `=COUNTIF('Dispatch Monitoring'!I2:I2174,"Installation")`          |
| Repairs (Total)              | `=COUNTIF('Dispatch Monitoring'!I2:I2174,"Repair")`                |
| Pending (Installation)       | Count records where Type = Installation and Status = Pending       |
| Closed (Installation)        | Count records where Type = Installation and Status = Done          |
| Cancelled (Installation)     | Count records where Type = Installation and Status = Cancel        |
| Rescheduled (Installation)   | Count records where Type = Installation and Status = Resched       |
| For Follow-Up (Installation) | Count records where Type = Installation and Status = For Follow-Up |

### Installation Performance

| Field              | Description                  |
| ------------------ | ---------------------------- |
| Target Installs    | Monthly target installations |
| Actual Installs    | Completed installations      |
| Remaining Installs | Target - Actual              |
| June Performance   | Monthly total and percentage |
| July Performance   | Monthly total and percentage |

#### Percentage Formula

```excel
=(Actual / Target)
```

---

## Technical Team Performance

### Fields

| Field                    | Description                       |
| ------------------------ | --------------------------------- |
| Staff Name               | Technician name                   |
| Install Count            | Total installations completed     |
| Repair Count             | Total repairs completed           |
| Total Jobs               | Install + Repair                  |
| Performance Percentage   | `(Install + Repair) / Total Jobs` |
| Target Per Day           | Daily target                      |
| Target Per Month         | Daily target × 26 working days    |
| Percentage of Production | Total Jobs / Monthly Target       |
| Per Day Average          | Daily average output              |

### Formulas

#### Total

```excel
=SUM(Install, Repair)
```

#### Performance Percentage

```excel
=(Install + Repair) / Total
```

#### Target Per Month

```excel
=TargetPerDay * 26
```

#### Percentage of Production

```excel
=TotalJobs / MonthlyTarget
```

#### Per Day Average

```excel
=TotalJobs / WorkingDays
```

---

## Admin Performance

### Fields

| Field                      | Description               |
| -------------------------- | ------------------------- |
| Admin Name                 | CSR/Admin name            |
| Number of Dispatch Handled | Total dispatches assigned |
| Number of Dispatch Closed  | Completed dispatches      |
| Number of Concerns Handled | Total concerns received   |
| Number of Concerns Closed  | Closed concerns           |

### Metrics

| Formula          | Description                                    |
| ---------------- | ---------------------------------------------- |
| Dispatch Handled | Count assigned dispatches                      |
| Dispatch Closed  | Count completed Installation/Repair dispatches |
| Concerns Handled | Count concern records                          |
| Concerns Closed  | Count completed concern records                |

### Performance Formulas

```excel
=DispatchClosed / DispatchHandled
```

```excel
=ConcernsClosed / ConcernsHandled
```

---

# Monthly Dashboard Tab

## Overview

### Summary

| Field            |
| ---------------- |
| As Of Date       |
| Installs (Total) |
| Repairs (Total)  |

### Technical Team

| Field                    |
| ------------------------ |
| Staff                    |
| Install                  |
| Repair                   |
| Total                    |
| Percentage               |
| Target Per Day           |
| Target Per Month         |
| Percentage of Production |
| Per Day Average          |

### Admin Team

| Field            |
| ---------------- |
| Admin            |
| Dispatch Handled |
| Dispatch Closed  |
| Concerns Handled |
| Concerns Closed  |

---

# Dispatch Monitoring

| Field           | Type         |
| --------------- | ------------ |
| Date            | Date         |
| Client          | Manual Text  |
| Address         | Manual Text  |
| Contact Number  | Manual Text  |
| Concern         | Manual Text  |
| Sales Agent     | Manual Text  |
| CSR             | Smart Chip   |
| Chat Type       | Smart Chip   |
| Type            | Smart Chip   |
| Team            | Multi-Select |
| Status          | Smart Chip   |
| Remarks         | Manual Text  |
| Time Start      | Manual Text  |
| Time Accomplish | Manual Text  |
| Duration        | Formula      |

### Chat Type Options

* Inquiry
* Concern
* For Installation

### Type Options

* Repair
* Installation
* Transition
* Mainline Repair
* OSP
* Pull Out

### Status Options

* Pending
* Done
* Cancel
* Resched
* Transition
* For Follow-Up

### Duration Formula

```excel
=TimeAccomplish - TimeStart
```

---

# Internet Install Monitoring

| Field          | Type        |
| -------------- | ----------- |
| Date           | Date        |
| Client         | Manual Text |
| Address        | Manual Text |
| Contact Number | Manual Text |
| Concern        | Manual Text |
| Sales Agent    | Manual Text |
| CSR In Charge  | Smart Chip  |
| Status         | Smart Chip  |
| Remarks        | Manual Text |
| Team           | Manual Text |

### Status Options

* Pending
* Close
* Cancelled
* For Follow-Up
* Rescheduled
* No Action Yet

---

# Client Concerns Monitoring

| Field          | Type           |
| -------------- | -------------- |
| Date           | Date           |
| Ticket Number  | Auto Generated |
| Client         | Manual Text    |
| Address        | Manual Text    |
| Contact Number | Manual Text    |
| CSR In Charge  | Smart Chip     |
| Concern        | Manual Text    |
| Actions Taken  | Manual Text    |
| Status         | Smart Chip     |
| Remarks        | Manual Text    |

### Ticket Format

```text
GPT-0000115
GPT-0000116
GPT-0000117
```

### Status Options

* Pending
* Close

---

# Cignal Play Install Monitoring

| Field          | Type        |
| -------------- | ----------- |
| Date           | Date        |
| Client         | Manual Text |
| Address        | Manual Text |
| Contact Number | Manual Text |
| Concern        | Manual Text |
| Sales Agent    | Manual Text |
| CSR In Charge  | Smart Chip  |
| Status         | Smart Chip  |
| Remarks        | Manual Text |
| Team           | Manual Text |

### Status Options

* Pending
* Close
* Cancelled
