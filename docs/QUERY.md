# Read-only Query data

`Query("query_data", ...)` lets an OpenUI card load rows from one endpoint
chosen by the Hermes profile owner. The browser and model cannot choose another
host, change the HTTP method, or retrieve the stored bearer token.

The plugin does not add model-callable data tools. Returned Query rows go from
the configured endpoint through the Hermes plugin bridge to the browser card;
they do not enter the model transcript.

## Configure

Open the Hermes plugin settings for `hermes-openui` and set:

- **Read-only query URL** — the HTTPS endpoint the bridge may call.
- **Query bearer token** — optional credential for that endpoint.

The equivalent non-secret configuration is:

```yaml
plugins:
  entries:
    hermes-openui:
      settings:
        query_url: "https://data.example.com/v1/rows"
```

The token field is a Hermes secret. Hermes stores it in the profile's `.env` as
`HERMES_OPENUI_QUERY_TOKEN` and never returns it to the browser.

Restart the gateway after changing plugin configuration outside the settings
page:

```sh
hermes gateway restart
```

## Endpoint contract

The configured endpoint must:

- accept `GET`
- return a JSON object with a top-level `rows` array
- make every item in `rows` a JSON object
- respond within 10 seconds
- return no more than 1 MB and 5,000 rows
- avoid redirects

Example response:

```json
{
  "rows": [
    {"region": "North", "amount": 42},
    {"region": "South", "amount": 37}
  ]
}
```

The URL must be credential-free HTTPS. Plain HTTP is accepted only for loopback
hosts during local development. URLs with embedded credentials or fragments
are rejected. Existing query parameters in the configured URL are kept, and the
OpenUI arguments are appended. Redirects are never followed.

## Arguments

The argument object supplied to `Query` becomes URL query parameters:

```text
rows = Query("query_data", {window: "30d", region: ["North", "South"]}, {rows: []})
```

That request adds:

```text
window=30d&region=North&region=South
```

Argument names must start with a letter and contain only letters, digits, and
underscores. The complete contract is:

| Field | Limit |
|---|---:|
| Arguments per request | 32 |
| Name length | 64 characters |
| Values per array | 50 |
| String value length | 2,000 characters |
| Result rows | 5,000 |
| Response body | 1 MB |
| Request timeout | 10 seconds |

Values must be strings, numbers, booleans, or `null`, including inside arrays.
Booleans are sent as lowercase `true` or `false`; `null` is sent as an empty
string.

## Security boundary

The browser calls the authenticated Hermes plugin route:

```text
POST /api/plugins/hermes-openui/query
```

with:

```json
{"arguments": {"window": "30d"}}
```

The gateway then performs the single configured `GET` request. The Query URL
and bearer credential remain in the Hermes profile.

`GET /api/plugins/hermes-openui/capabilities` reports whether a valid endpoint
is configured without exposing its URL:

```json
{"query_data": {"configured": true}}
```

## Use returned data

Use only fields that the endpoint actually returns. If the request does not
identify the available fields, keep the answer textual or ask for the field
names.

Compute displayed values from the returned rows with OpenUI functions such as
`@Sum`, `@Count`, `@GroupBy`, `@Bucket`, `@Top`, `@Stats`, and `@Change`:

```text
root = Col([title, table], 4)
title = Title("Recent totals", "xl")
data = Query("query_data", {window: "30d"}, {rows: []})
table = Table(["Region", "Amount"], @Each(data.rows, "row", [row.region, row.amount]))
```

Never fill missing rows, columns, or values with invented data. When the user
asks for a demo, label synthetic rows visibly as **Demo data**.

## Errors and retry

The card shows a loading state while the request runs. Missing configuration,
network failure, non-2xx responses, redirects, invalid JSON, invalid row shape,
timeouts, and size-limit violations produce a visible data error with a retry
control.

Normal answers do not replace an unavailable configured source with fixture
rows. The same rule applies to screenshots and tests: any synthetic row set must
be labeled as demo data.
