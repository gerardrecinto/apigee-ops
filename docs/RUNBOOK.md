# Runbook

## Renew a certificate

1. Get the new certificate chain (leaf first) and key from your CA.
2. Check it: `python -m apigee_ops.certs check --cert new.pem --key new.key --host api.example.com`
   Exit 0 is clean, 2 is a warning (under 30 days left), 1 is an error.
3. Write it: `python -m apigee_ops.certs renew --project PROJECT --secret apigee-tls-test --cert new.pem --key new.key --host api.example.com`
   It prints `written`, `unchanged` or `rejected` with the reasons. Rejected means nothing was written.
4. Test first, prod second. The secret is the source of truth; loading it into the Apigee keystore is the deploy step of your pipeline.

Needs `pip install -e ".[gcp]"` and Application Default Credentials that can add secret versions.

## Capacity check

`python -m apigee_ops.capacity analytics.csv --capacity-tps N` exits 1 when the straight-line estimate says the planning threshold is under 30 days away, so a scheduled job can page on it. Export the CSV from Apigee analytics with columns `timestamp,proxy,tps,p99_ms,error_rate`.

## Weekly gateway report

`python -m apigee_ops.logreport gateway.log` reads the lines `ML-Splunk` writes. The report prints how many lines it skipped; a jump in that number means the policy message and the parser have drifted.

## Deploy a proxy

`python -m apigee_ops.deploy --org ORG --env test --proxy-dir proxies/orders-api` prints what it would do. Add `--apply` to send it. The bearer token comes from `gcloud auth print-access-token`.
