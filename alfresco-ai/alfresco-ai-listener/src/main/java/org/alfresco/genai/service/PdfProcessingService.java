package org.alfresco.genai.service;

import com.adobe.pdfservices.operation.PDFServices;
import com.adobe.pdfservices.operation.PDFServicesMediaType;
import com.adobe.pdfservices.operation.PDFServicesResponse;
import com.adobe.pdfservices.operation.auth.Credentials;
import com.adobe.pdfservices.operation.auth.ServicePrincipalCredentials;
import com.adobe.pdfservices.operation.exception.SDKException;
import com.adobe.pdfservices.operation.exception.ServiceApiException;
import com.adobe.pdfservices.operation.exception.ServiceUsageException;
import com.adobe.pdfservices.operation.io.Asset;
import com.adobe.pdfservices.operation.io.StreamAsset;
import com.adobe.pdfservices.operation.pdfjobs.jobs.PDFAccessibilityCheckerJob;
import com.adobe.pdfservices.operation.pdfjobs.result.PDFAccessibilityCheckerResult;
import org.apache.commons.io.IOUtils;
import org.json.JSONObject;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.io.*;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

/**
 * Service to process PDFs using Adobe PDF Services API.
 */
@Service
public class PdfProcessingService {

    private static final Logger LOG = LoggerFactory.getLogger(PdfProcessingService.class);
    private final Credentials credentials;
    private final PDFServices pdfServices;

    public PdfProcessingService() {
        this.credentials = new ServicePrincipalCredentials(
            System.getenv("PDF_SERVICES_CLIENT_ID"),
            System.getenv("PDF_SERVICES_CLIENT_SECRET")
        );
        this.pdfServices = new PDFServices(credentials);
    }

    /**
     * Runs the Adobe PDF Accessibility Checker on a given document.
     *
     * @param inputStream The input stream of the document.
     * @return The extracted accessibility score from the report.
     */
    public String checkPdfAccessibility(InputStream inputStream) {
        try {
            // Upload the PDF file to Adobe Services
            Asset asset = pdfServices.upload(inputStream, PDFServicesMediaType.PDF.getMediaType());

            // Create a new job instance for accessibility checking
            PDFAccessibilityCheckerJob job = new PDFAccessibilityCheckerJob(asset);
            
            // Submit the job
            String location = pdfServices.submit(job);
            PDFServicesResponse<PDFAccessibilityCheckerResult> response = pdfServices.getJobResult(location, PDFAccessibilityCheckerResult.class);

            // Get the resulting accessibility report
            Asset reportAsset = response.getResult().getReport();
            StreamAsset reportStreamAsset = pdfServices.getContent(reportAsset);
            
            // Save report and return score
            return processReport(reportStreamAsset);

        } catch (ServiceApiException | SDKException | ServiceUsageException e) {
            LOG.error("Error during Adobe PDF accessibility analysis", e);
            return "Error";
        }
    }

    /**
     * Processes the accessibility report, extracts the score, and saves the report.
     * 
     * @param reportStreamAsset The accessibility report stream asset.
     * @return The extracted accessibility score.
     */
    private String processReport(StreamAsset reportStreamAsset) {
        try (InputStream reportStream = reportStreamAsset.getInputStream()) {
            // Convert JSON response to String
            String jsonReport = IOUtils.toString(reportStream, "UTF-8");
            JSONObject jsonObject = new JSONObject(jsonReport);
            
            LOG.info("Logging Adobe API Accessibility Report");
            LOG.info(jsonReport);
            
            JSONObject summary = jsonObject.optJSONObject("Summary");
            String extractedDescription = summary != null
                    ? summary.optString("Description", "No description found")
                    : "No summary section found";


            LOG.info("extractedDescription");
            LOG.info(extractedDescription);

            return extractedDescription;

        } catch (IOException e) {
            LOG.error("Error processing accessibility report", e);
            return "Error";
        }
    }
}
