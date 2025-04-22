package org.alfresco.genai.event;

import java.io.ByteArrayInputStream;
import java.io.InputStream;

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
import org.alfresco.genai.service.NodeUpdateService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;

/**
 * The {@code ContentA11yCreatedHandler} class listens for Alfresco events and 
 * triggers accessibility scoring for documents via the Alfresco REST API.
 */
@Component
public class ContentA11yCreatedHandler implements OnNodeCreatedEventHandler {

    private static final Logger LOG = LoggerFactory.getLogger(ContentA11yCreatedHandler.class);

    @Value("${content.service.a11y.aspect}")
    private String a11yAspect;

    @Autowired
    private NodesApi nodesApi;

    @Autowired
    NodeUpdateService nodeUpdateService;

    @Autowired
    private A11yScore testScore;

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

            LOG.info("Node-Created-Handler: A11y (Accessibility)-scoring document {}", uuid);
            
            // Make Score object from InputStream
            testScore.checkDocument(documentContent);

            nodeUpdateService.updateNodeA11yScore(uuid, testScore);

            LOG.info("Document {} has been created with a11y-score and model", uuid);
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
