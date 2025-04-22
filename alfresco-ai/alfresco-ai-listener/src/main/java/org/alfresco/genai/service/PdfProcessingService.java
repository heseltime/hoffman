package org.alfresco.genai.service;

import com.adobe.pdfservices.operation.*;
import com.adobe.pdfservices.operation.auth.*;
import com.adobe.pdfservices.operation.exception.*;
import com.adobe.pdfservices.operation.io.*;
import com.adobe.pdfservices.operation.pdfjobs.jobs.*;
import com.adobe.pdfservices.operation.pdfjobs.result.*;

import org.apache.commons.io.IOUtils;
import org.json.JSONObject;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;

@Service
public class PdfProcessingService {

    private static final Logger LOG = LoggerFactory.getLogger(PdfProcessingService.class);

    private final PDFServices pdfServices;
    private final NodeStorageService nodeStorageService;

    public PdfProcessingService(NodeStorageService nodeStorageService) {
        this.pdfServices = new PDFServices(new ServicePrincipalCredentials(
            System.getenv("PDF_SERVICES_CLIENT_ID"),
            System.getenv("PDF_SERVICES_CLIENT_SECRET")
        ));
        this.nodeStorageService = nodeStorageService;
    }

    public JSONObject getAccessibilityReportObject(InputStream inputStream) {
        try {
            // Upload and submit PDF to Adobe API
            Asset asset = pdfServices.upload(inputStream, PDFServicesMediaType.PDF.getMediaType());
            PDFAccessibilityCheckerJob job = new PDFAccessibilityCheckerJob(asset);
            String location = pdfServices.submit(job);
            PDFServicesResponse<PDFAccessibilityCheckerResult> response = pdfServices.getJobResult(location, PDFAccessibilityCheckerResult.class);
            StreamAsset reportStreamAsset = pdfServices.getContent(response.getResult().getReport());

            // Convert to JSON
            String jsonReport = IOUtils.toString(reportStreamAsset.getInputStream(), StandardCharsets.UTF_8);

            JSONObject jsonObject = new JSONObject(jsonReport);
            
            //String description = jsonObject.optJSONObject("Summary").optString("Description", "No summary");

            LOG.info("✅ A11y returned");

            return jsonObject;

        } catch (Exception e) {
            LOG.error("❌ Error running accessibility check or saving report", e);
            return null;
        }
    }

    public String checkPdfAccessibility(String originalNodeId, InputStream inputStream) {
        try {
            // Upload and submit PDF to Adobe API
            Asset asset = pdfServices.upload(inputStream, PDFServicesMediaType.PDF.getMediaType());
            PDFAccessibilityCheckerJob job = new PDFAccessibilityCheckerJob(asset);
            String location = pdfServices.submit(job);
            PDFServicesResponse<PDFAccessibilityCheckerResult> response = pdfServices.getJobResult(location, PDFAccessibilityCheckerResult.class);
            StreamAsset reportStreamAsset = pdfServices.getContent(response.getResult().getReport());

            // Convert to JSON
            String jsonReport = IOUtils.toString(reportStreamAsset.getInputStream(), StandardCharsets.UTF_8);
            JSONObject jsonObject = new JSONObject(jsonReport);
            String description = jsonObject.optJSONObject("Summary").optString("Description", "No summary");

            // Build target path in My Files
            String reportFolderId = nodeStorageService.ensureMyFilesReportFolder(originalNodeId);

            // Build report filename
            String originalName = nodeStorageService.getNodeTitle(originalNodeId)
                .orElse("document") + ".a11y-report.json";

            String reportNodeId = nodeStorageService.createOrUpdateJsonNode(reportFolderId, originalName, jsonReport);

            LOG.info("✅ A11y report saved to folder {} with name {}", reportFolderId, originalName);

            // Not working yet
            //nodeStorageService.linkDocumentToFolderAsReference(originalNodeId, reportFolderId); // reportFolder in "My Files"

            return description;

        } catch (Exception e) {
            LOG.error("❌ Error running accessibility check or saving report", e);
            return "Error";
        }
    }
}
