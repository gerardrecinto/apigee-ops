// Total time Apigee spent on this request, in milliseconds, for the log line.
var start = parseInt(context.getVariable("client.received.start.timestamp"), 10);
context.setVariable("log.latency_ms", Date.now() - start);
