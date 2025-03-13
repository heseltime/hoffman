package org.alfresco.genai.model;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;

import org.alfresco.genai.event.AbstractPictureTypeHandler;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * The {@code A11yScore} class represents an accessibility score assigned to a document.
 * It calculates a score based on document content analysis.
 */
public class A11yScore {

    /**
     * Logger for logging information and error messages.
     */
    private static final Logger LOG = LoggerFactory.getLogger(AbstractPictureTypeHandler.class);

    /**
     * The score assigned to the document.
     */
    private String score;

    /**
     * The model (or API) used for scoring.
     */
    private String model;

    /**
     * Constructs an {@code A11yScore} by analyzing the document content.
     *
     * @param inputStream The input stream of the document content.
     */
    public A11yScore(InputStream inputStream) {
        this.score = analyzeDocument(inputStream);
        this.model = "Basic A11y Model v1"; // You can change this based on your actual model
    }

    /**
     * Analyzes the document content and computes an accessibility score.
     *
     * @param inputStream The input stream of the document.
     * @return The computed accessibility score.
     */
    private String analyzeDocument(InputStream inputStream) {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(inputStream))) {
            StringBuilder content = new StringBuilder();
            String line;
            int wordCount = 0;

            while ((line = reader.readLine()) != null) {
                content.append(line).append("\n");
                LOG.info("A11y-line: {}", line);
                wordCount += line.split("\\s+").length;
            }

            // Simulated scoring logic: more words = higher complexity (worse accessibility)
            // TODO: Adobe API call here to separate package or service
            int calculatedScore = Math.max(100 - wordCount / 10, 0);

            return String.valueOf(calculatedScore);

        } catch (IOException e) {
            e.printStackTrace();
            return "Error";
        }
    }

    /**
     * Gets the accessibility score.
     *
     * @return The score text.
     */
    public String getScore() {
        return score;
    }

    /**
     * Sets the accessibility score.
     *
     * @param score The score text.
     * @return This {@code A11yScore} instance for method chaining.
     */
    public A11yScore score(String score) {
        this.score = score;
        return this;
    }

    /**
     * Gets the model used for scoring.
     *
     * @return The model name.
     */
    public String getModel() {
        return model;
    }

    /**
     * Sets the model used for scoring.
     *
     * @param model The model name.
     * @return This {@code A11yScore} instance for method chaining.
     */
    public A11yScore model(String model) {
        this.model = model;
        return this;
    }
}
