package org.alfresco.genai.service;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.Arrays;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

import org.alfresco.genai.model.A11yScore;
import org.alfresco.genai.model.Answer;
import org.alfresco.genai.model.Description;
import org.alfresco.genai.model.Summary;
import org.alfresco.genai.model.Term;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.json.JsonParser;
import org.springframework.boot.json.JsonParserFactory;
import org.springframework.stereotype.Service;

import jakarta.annotation.PostConstruct;
import okhttp3.HttpUrl;
import okhttp3.MediaType;
import okhttp3.MultipartBody;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

/**
 * The {@code GenAiClient} class is a Spring service that interacts with the GenAI service to obtain document summaries
 * and answers to specific questions. It uses an {@link OkHttpClient} to perform HTTP requests to the GenAI service
 * endpoint, and it is configured with properties such as the GenAI service URL and request timeout.
 */
@Service
public class GenAiClient {

    private static final Logger LOG = LoggerFactory.getLogger(NodeStorageService.class);

    /**
     * The base URL of the GenAI service obtained from configuration.
     */
    @Value("${genai.url}")
    String genaiUrl;

    /**
     * The request timeout for GenAI service requests obtained from configuration.
     */
    @Value("${genai.request.timeout}")
    Integer genaiTimeout;

    /**
     * Static instance of {@link JsonParser} to parse JSON responses from the GenAI service.
     */
    static final JsonParser JSON_PARSER = JsonParserFactory.getJsonParser();

    /**
     * The OkHttpClient instance for making HTTP requests to the GenAI service.
     */
    OkHttpClient client;

    /**
     * Initializes the OkHttpClient with specified timeouts during bean creation.
     */
    @PostConstruct
    public void init() {
        client = new OkHttpClient()
                .newBuilder()
                .connectTimeout(30, TimeUnit.SECONDS)
                .readTimeout(genaiTimeout, TimeUnit.SECONDS)
                .build();
    }

    /**
     * Retrieves a document summary from the GenAI service for the provided PDF file.
     *
     * @param pdfFile The PDF file for which the summary is requested.
     * @return A {@link Summary} object containing the summary, tags, and model information.
     * @throws IOException If an I/O error occurs during the HTTP request or response processing.
     */
    public Summary getSummary(File pdfFile) throws IOException {

        RequestBody requestBody = new MultipartBody
                .Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("file", pdfFile.getName(), RequestBody.create(pdfFile, MediaType.parse("application/pdf")))
                .build();

        Request request = new Request
                .Builder()
                .url(genaiUrl + "/summary")
                .post(requestBody)
                .build();

        String response = client.newCall(request).execute().body().string();
        Map<String, Object> aiResponse = JSON_PARSER.parseMap(response);
        return new Summary()
                .summary(aiResponse.get("summary").toString().trim())
                .tags(Arrays.asList(aiResponse.get("tags").toString().split(",", -1)))
                .model(aiResponse.get("model").toString());

    }

    /**
     * Retrieves an answer to a specific question from the GenAI service for the provided PDF file.
     *
     * @param pdfFile   The PDF file containing the document related to the question.
     * @param question  The question for which an answer is requested.
     * @return An {@link Answer} object containing the answer and the model information.
     * @throws IOException If an I/O error occurs during the HTTP request or response processing.
     */
    public Answer getAnswer(File pdfFile, String question) throws IOException {

        RequestBody requestBody = new MultipartBody
                .Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("file", pdfFile.getName(), RequestBody.create(pdfFile, MediaType.parse("application/pdf")))
                .build();

        HttpUrl httpUrl = HttpUrl.parse(genaiUrl + "/prompt")
                .newBuilder()
                .addQueryParameter("prompt", question)
                .build();

        Request request = new Request
                .Builder()
                .url(httpUrl)
                .post(requestBody)
                .build();

        String response = client.newCall(request).execute().body().string();
        Map<String, Object> aiResponse = JSON_PARSER.parseMap(response);
        return new Answer()
                .answer(aiResponse.get("answer").toString().trim())
                .model(aiResponse.get("model").toString());

    }

    /**
     * Selects a term from a term list using the GenAI service for the provided PDF file.
     *
     * @param pdfFile   The PDF file containing the document related to the question.
     * @param termList  List of terms that includes options to be selected.
     * @return An {@link Term} object containing the term and the model information.
     * @throws IOException If an I/O error occurs during the HTTP request or response processing.
     */
    public Term getTerm(File pdfFile, String termList) throws IOException {

        RequestBody requestBody = new MultipartBody
                .Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("file", pdfFile.getName(), RequestBody.create(pdfFile, MediaType.parse("application/pdf")))
                .build();

        HttpUrl httpUrl = HttpUrl.parse(genaiUrl + "/classify")
                .newBuilder()
                .addQueryParameter("termList", "\"" + termList + "\"")
                .build();

        Request request = new Request
                .Builder()
                .url(httpUrl)
                .post(requestBody)
                .build();

        String response = client.newCall(request).execute().body().string();

        Map<String, Object> aiResponse = JSON_PARSER.parseMap(response);
        return new Term()
                .term(aiResponse.get("term").toString().trim())
                .model(aiResponse.get("model").toString());

    }

    /**
     * Describes a picture using the GenAI service for the provided picture file.
     *
     * @param pictureFile   The picture file containing the image related to the question.
     * @return An {@link Description} object containing the description and the model information.
     * @throws IOException If an I/O error occurs during the HTTP request or response processing.
     */
    public Description getDescription(File pictureFile) throws IOException {

        RequestBody requestBody = new MultipartBody
                .Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("image", pictureFile.getName(), RequestBody.create(pictureFile, MediaType.parse("Binary data")))
                .build();

        HttpUrl httpUrl = HttpUrl.parse(genaiUrl + "/describe")
                .newBuilder()
                .build();

        Request request = new Request
                .Builder()
                .url(httpUrl)
                .post(requestBody)
                .build();

        String response = client.newCall(request).execute().body().string();

        Map<String, Object> aiResponse = JSON_PARSER.parseMap(response);
        return new Description()
                .description(aiResponse.get("description").toString().trim())
                .model(aiResponse.get("model").toString());

    }

    public File getAccessibleDocumentVersion(InputStream documentContent, A11yScore testScore) throws IOException {
        // Convert InputStream to temporary File (OkHttp needs a concrete file or byte array )
        File tempFile = File.createTempFile("doc-upload-", UUID.randomUUID().toString() + ".pdf");
        Files.copy(documentContent, tempFile.toPath(), StandardCopyOption.REPLACE_EXISTING);
    
        File resultPdf = null;
    
        try {
            // Convert testScore to JSON
            MediaType mediaType = MediaType.parse("application/json");
            String scoreJson = testScore.toJsonString();
    
            // Prepare the multipart request
            RequestBody requestBody = new MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("file", tempFile.getName(),
                    RequestBody.create(tempFile, MediaType.parse("application/pdf")))
                .addFormDataPart("metadata", null,
                    RequestBody.create(scoreJson, mediaType))
                .build();
    
            Request request = new Request.Builder()
                .url(genaiUrl + "/accessible-document-version")
                .post(requestBody)
                .build();
    
            try (Response response = client.newCall(request).execute()) {
                if (!response.isSuccessful()) {
                    throw new IOException("Unexpected response from GenAI: " + response);
                }
    
                // Save the returned PDF stream to a new temp file: this save my also not be needed
                resultPdf = File.createTempFile("accessible-version-", ".pdf");
                try (InputStream is = response.body().byteStream()) {
                    Files.copy(is, resultPdf.toPath(), StandardCopyOption.REPLACE_EXISTING);
                }
    
                LOG.info("✅ GenAI returned accessible PDF, stored at: {}", resultPdf.getAbsolutePath());
            }
    
        } finally {
            // Clean up the uploaded source file
            if (tempFile.exists()) {
                tempFile.delete();
            }
        }
    
        return resultPdf; // Return the generated PDF file for further processing
    }    

}
