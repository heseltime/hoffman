package org.alfresco.genai.event;

import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.io.File;

import org.alfresco.core.handler.NodesApi;
import org.alfresco.event.sdk.handling.filter.EventFilter;
import org.alfresco.event.sdk.handling.filter.NodeAspectFilter;
import org.alfresco.event.sdk.handling.filter.NodeTypeFilter;
import org.alfresco.event.sdk.handling.handler.OnNodeCreatedEventHandler;
import org.alfresco.event.sdk.model.v1.model.DataAttributes;
import org.alfresco.event.sdk.model.v1.model.NodeResource;
import org.alfresco.event.sdk.model.v1.model.RepoEvent;
import org.alfresco.event.sdk.model.v1.model.Resource;
import org.alfresco.genai.model.A11yScore;
import org.alfresco.genai.service.GenAiClient;
import org.alfresco.genai.service.NodeUpdateService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Base64;

/**
 * The {@code ContentA11yCreatedHandler} class listens for Alfresco events and 
 * triggers accessibility scoring for documents via the Alfresco REST API.
 */
@Component
public class ContentA11yCreatedHandler implements OnNodeCreatedEventHandler {

    private static final Logger LOG = LoggerFactory.getLogger(ContentA11yCreatedHandler.class);

    @Value("${content.service.a11y.aspect}")
    private String a11yAspect;

    @Value("${accessibility.pipeline.max.checking.retries}")
    private String MAX_RETRIES_ACCESSIBILITY_CHECKING_LOOP;

    @Autowired
    private NodesApi nodesApi;

    @Autowired
    private NodeUpdateService nodeUpdateService;

    @Autowired
    private A11yScore testScore;

    @Autowired
    private GenAiClient genAiClient;

    /**
     * Handles the node creation event triggered by the system. Fetches document content
     * via REST API and initiates the accessibility scoring process.
     *
     * @param repoEvent The event containing information about the created node.
     */
    @Override
    public void handleEvent(final RepoEvent<DataAttributes<Resource>> repoEvent) {
        NodeResource nodeResource = (NodeResource) repoEvent.getData().getResource();
        String uuid = nodeResource.getId();

        try {
            // Fetch document content using Alfresco REST API
            ResponseEntity<org.springframework.core.io.Resource> response = nodesApi.getNodeContent(uuid, false, null, null);
            org.springframework.core.io.Resource resource = response.getBody();

            if (resource == null || !resource.exists()) {
                LOG.warn("No content found for document with UUID {}", uuid);
                return;
            }

            // Convert Resource to InputStream
            InputStream documentContent = resource.getInputStream();
            byte[] contentBytes = documentContent.readAllBytes();

            LOG.info("Node-Created-Handler: A11y (Accessibility)-scoring document {}", uuid);
            
            // Make Score object from InputStream
            testScore.checkDocument(new ByteArrayInputStream(contentBytes));

            nodeUpdateService.updateNodeA11yScore(uuid, testScore);

            // Get accessible PDF from GenAI stack
            File accessibleVersion = genAiClient.getAccessibleDocumentVersion(new ByteArrayInputStream(contentBytes), testScore);

            // ✅ Do something useful with the returned PDF file
            // For example: store it in Alfresco as a new version or related node
            if (accessibleVersion != null && accessibleVersion.exists()) {
                LOG.info("Uploading accessible version of document {} to Alfresco", uuid);
                //nodeUpdateService.storeAccessibleVersion(uuid, accessibleVersion);

                // Try to interpret content as UTF-8 text
                try {
                    byte[] accessibleBytes = Files.readAllBytes(accessibleVersion.toPath());
                    String accessibleContent = new String(accessibleBytes, StandardCharsets.UTF_8);
                    LOG.info("Accessible version content as UTF-8 text:\n{}", accessibleContent);
                } catch (Exception textEx) {
                    // If not readable as text, log Base64 preview
                    try {
                        byte[] accessibleBytes = Files.readAllBytes(accessibleVersion.toPath());
                        String base64Preview = Base64.getEncoder().encodeToString(Arrays.copyOf(accessibleBytes, Math.min(100, accessibleBytes.length)));
                        LOG.info("Accessible version is binary. Base64 preview:\n{}", base64Preview);
                    } catch (IOException ioEx) {
                        LOG.error("Error reading accessible PDF file: {}", ioEx.getMessage(), ioEx);
                    }
                }

            } else {
                LOG.warn("GenAI returned null or missing accessible PDF for document {}", uuid);
            }

            LOG.info("Document {} has been created with a11y-score and accessible version", uuid);
        } catch (Exception e) {
            LOG.error("Failed to fetch content for document {}: {}", uuid, e.getMessage());
        }
    }

    /**
     * Specifies the event filter to determine which node creation events this handler should process.
     *
     * @return An {@link EventFilter} representing the filter criteria for node creation events.
     */
    @Override
    public EventFilter getEventFilter() {
        return NodeAspectFilter.of(a11yAspect)
                .and(NodeTypeFilter.of("cm:content"));
    }
}
