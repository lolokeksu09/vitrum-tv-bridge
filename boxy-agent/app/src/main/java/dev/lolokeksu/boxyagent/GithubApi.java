package dev.lolokeksu.boxyagent;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public final class GithubApi {
    private static final String HOST = "https://api.github.com";
    private final String token;

    public GithubApi(String token) {
        if (token == null || token.length() < 8) throw new IllegalArgumentException("Missing token");
        this.token = token;
    }

    private String request(String method, String path, JSONObject payload) throws IOException {
        // Host never comes from an issue. The repo was already strictly validated.
        if (!path.startsWith("/repos/") || path.contains("..") || path.contains("//")
                || path.length() > 300)
            throw new IOException("Invalid GitHub endpoint");
        HttpURLConnection connection = (HttpURLConnection) new URL(HOST + path).openConnection();
        connection.setInstanceFollowRedirects(false);
        connection.setConnectTimeout(7000);
        connection.setReadTimeout(9000);
        connection.setRequestMethod(method);
        connection.setRequestProperty("Authorization", "Bearer " + token);
        connection.setRequestProperty("Accept", "application/vnd.github+json");
        connection.setRequestProperty("User-Agent", "BOXY-Agent/0.1");
        connection.setRequestProperty("X-GitHub-Api-Version", "2022-11-28");
        try {
            if (payload != null) {
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                connection.setDoOutput(true);
                byte[] bytes = payload.toString().getBytes(StandardCharsets.UTF_8);
                if (bytes.length > 4096) throw new IOException("Request too large");
                try (OutputStream os = connection.getOutputStream()) { os.write(bytes); }
            }
            int code = connection.getResponseCode();
            if (code < 200 || code >= 300) throw new IOException("GitHub HTTP " + code);
            try (InputStream input = connection.getInputStream()) {
                ByteArrayOutputStream output = new ByteArrayOutputStream();
                byte[] buf = new byte[8192]; int read;
                while ((read = input.read(buf)) >= 0) {
                    if (output.size() + read > 512_000) throw new IOException("Response too large");
                    output.write(buf, 0, read);
                }
                return output.toString("UTF-8");
            }
        } finally {
            connection.disconnect();
        }
    }

    public JSONObject repository(String repo) throws Exception {
        if (!AgentPolicy.allowedRepo(repo)) throw new IOException("Invalid repo");
        return new JSONObject(request("GET", "/repos/" + repo, null));
    }
    public JSONArray openIssues(String repo) throws Exception {
        return new JSONArray(request("GET", "/repos/" + repo
                + "/issues?state=open&sort=created&direction=asc&per_page=40", null));
    }
    public void comment(String repo, int number, String comment) throws Exception {
        if (comment == null || comment.length() > 500) throw new IOException("Comment too long");
        request("POST", "/repos/" + repo + "/issues/" + number + "/comments",
                new JSONObject().put("body", comment));
    }
    public void close(String repo, int number) throws Exception {
        request("PATCH", "/repos/" + repo + "/issues/" + number,
                new JSONObject().put("state", "closed"));
    }
}
