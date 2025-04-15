package org.alfresco.genai.model;

import org.alfresco.genai.service.PdfProcessingService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.io.InputStream;

/**
 * The {@code A11yScore} class represents an accessibility score assigned to a document.
 * It calculates a score based on document content analysis using the Adobe PDF Accessibility Checker API.
 */
@Component
public class A11yScore {

    private static final Logger LOG = LoggerFactory.getLogger(A11yScore.class);

    private String score;
    private String model;

    @Autowired
    PdfProcessingService pdfProcessingService;

    /**
     * Analyzes the document using Adobe PDF Accessibility Checker API and sets score.
     *
     * @param inputStream The input stream of the document.
     */
    public void analyzeDocument(InputStream inputStream) {
        LOG.info("Starting accessibility analysis using Adobe API...");
        score = pdfProcessingService.checkPdfAccessibility(inputStream);
    }

    public String getScore() {
        return score;
    }

    public String getModel() {
        return model;
    }
}
