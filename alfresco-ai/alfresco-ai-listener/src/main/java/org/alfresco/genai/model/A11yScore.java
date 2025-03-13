package org.alfresco.genai.model;

import java.util.List;

/**
 * The {@code Description} class represents the result of description a picture using AI services.
 * It contains the description text and the model used for description.
 *
 * <p>This class follows the builder pattern, allowing for a fluent and readable way to construct instances.
 *
 */
public class A11yScore {

    /**
     * The score text content of the doc.
     */
    private String score;

    /**
     * The model (or API) used for scoring.
     */
    private String model;

    /**
     * Gets thescore text content of the doc.
     *
     * @return The score text.
     */
    public String getScore() {
        return score;
    }

    /**
     * Sets the score text content of the doc.
     *
     * @param score The score text.
     * @return This {@code Score} instance for method chaining.
     */
    public A11yScore score(String score) {
        this.score = score;
        return this;
    }

    /**
     * Gets the model used for score.
     *
     * @return The score model.
     */
    public String getModel() {
        return model;
    }

    /**
     * Sets the model used for score.
     *
     * @param model The score model.
     * @return This {@code Score} instance for method chaining.
     */
    public A11yScore model(String model) {
        this.model = model;
        return this;
    }

}
