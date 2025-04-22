package org.alfresco.genai.model;

import org.alfresco.genai.service.PdfProcessingService;
import org.json.JSONArray;
import org.json.JSONObject;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.io.InputStream;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * The {@code A11yScore} class represents an accessibility score assigned to a document.
 * It parses the accessibility report returned by Adobe PDF Services.
 */
@Component
public class A11yScore {

    private static final Logger LOG = LoggerFactory.getLogger(A11yScore.class);

    // Top-level summary fields
    private String score = "";
    private String model = "";

    private String summaryDescription;
    private int summaryNeedsManualCheck;
    private int summaryPassedManually;
    private int summaryFailedManually;
    private int summarySkipped;
    private int summaryPassed;
    private int summaryFailed;

    // Flattened rules, e.g. "Accessibility Permission Flag" -> "Passed"
    private final Map<String, String> ruleResults = new HashMap<>();

    @Autowired
    PdfProcessingService pdfProcessingService;

    public void analyzeDocument(String originalNodeId, InputStream inputStream) {
        LOG.info("Starting accessibility analysis using Adobe API...");
        score = pdfProcessingService.checkPdfAccessibility(originalNodeId, inputStream);
        model = "Adobe PDF Services API";
    }

    public void checkDocument(InputStream inputStream) {
        LOG.info("Starting accessibility checking using Adobe API and constructing A11yScore");

        JSONObject json = pdfProcessingService.getAccessibilityReportObject(inputStream);

        LOG.info(json.toString());

        // Extract summary
        JSONObject summary = json.optJSONObject("Summary");
        if (summary != null) {
            summaryDescription = summary.optString("Description", "");
            summaryNeedsManualCheck = summary.optInt("Needs manual check", 0);
            summaryPassedManually = summary.optInt("Passed manually", 0);
            summaryFailedManually = summary.optInt("Failed manually", 0);
            summarySkipped = summary.optInt("Skipped", 0);
            summaryPassed = summary.optInt("Passed", 0);
            summaryFailed = summary.optInt("Failed", 0);
        }

        // Extract rules from "Detailed Report"
        JSONObject detailedReport = json.optJSONObject("Detailed Report");
        if (detailedReport != null) {
            for (String category : detailedReport.keySet()) {
                JSONArray ruleArray = detailedReport.optJSONArray(category);
                if (ruleArray != null) {
                    for (int i = 0; i < ruleArray.length(); i++) {
                        JSONObject rule = ruleArray.optJSONObject(i);
                        if (rule != null) {
                            String ruleRaw = rule.optString("Rule", "");
                            String ruleName = toCamelCase(ruleRaw);

                            LOG.debug("🧩 Adding rule key: {}", ruleName);

                            String status = rule.optString("Status", "");
                            ruleResults.put(ruleName, status);
                        }
                    }
                }
            }
        }

        // score and model not used here
        score = "";
        model = "";
    }

    private String toCamelCase(String input) {
        StringBuilder result = new StringBuilder();
        for (String word : input.split("[^A-Za-z0-9]")) {
            if (!word.isEmpty()) {
                result.append(Character.toUpperCase(word.charAt(0)));
                if (word.length() > 1) {
                    result.append(word.substring(1));
                }
            }
        }
        return result.toString();
    }    

    // Getters for all fields
    public String getScore() {
        return score;
    }

    public String getModel() {
        return model;
    }

    public String getSummaryDescription() {
        return summaryDescription;
    }

    public int getSummaryNeedsManualCheck() {
        return summaryNeedsManualCheck;
    }

    public int getSummaryPassedManually() {
        return summaryPassedManually;
    }

    public int getSummaryFailedManually() {
        return summaryFailedManually;
    }

    public int getSummarySkipped() {
        return summarySkipped;
    }

    public int getSummaryPassed() {
        return summaryPassed;
    }

    public int getSummaryFailed() {
        return summaryFailed;
    }

    public Map<String, String> getRuleResults() {
        return ruleResults;
    }

    public String getRuleStatus(String ruleKey) {
        return ruleResults.get(ruleKey);
    }
}
