package org.alfresco.genai.event;
import java.io.IOException;
import java.io.File;
import java.io.InputStream;

import org.alfresco.core.handler.NodesApi;
import org.alfresco.event.sdk.handling.filter.AspectAddedFilter;
import org.alfresco.event.sdk.handling.filter.ContentChangedFilter;
import org.alfresco.event.sdk.handling.filter.EventFilter;
import org.alfresco.event.sdk.handling.filter.NodeAspectFilter;
import org.alfresco.event.sdk.handling.filter.NodeTypeFilter;
import org.alfresco.event.sdk.handling.handler.OnNodeCreatedEventHandler;
import org.alfresco.event.sdk.handling.handler.OnNodeUpdatedEventHandler;
import org.alfresco.event.sdk.model.v1.model.DataAttributes;
import org.alfresco.event.sdk.model.v1.model.NodeResource;
import org.alfresco.event.sdk.model.v1.model.RepoEvent;
import org.alfresco.event.sdk.model.v1.model.Resource;
import org.alfresco.genai.model.A11yScore;
import org.alfresco.genai.service.NodeStorageService;
import org.alfresco.genai.service.NodeUpdateService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;


/**
 * The {@code ContentClassifyUpdatedHandler} class is a Spring component that extends the {@link AbstractContentTypeHandler}
 * and implements the {@link OnNodeUpdatedEventHandler} interface. It is responsible for handling events triggered upon the
 * update of nodes with a specified content type, focusing on nodes with the "cm:content" type and a specific classified aspect.
 *
 * <p>This handler provides a detailed event filter definition using a combination of filters to identify relevant node
 * update events. The filter criteria include the presence of the accessibility aspect, the "cm:content" node type, content
 * changes, or the addition of the classified aspect.
 */
@Component
public class ContentA11yUpdatedHandler extends AbstractContentTypeHandler implements OnNodeUpdatedEventHandler {

    private static final Logger LOG = LoggerFactory.getLogger(ContentA11yCreatedHandler.class);

    @Value("${content.service.a11y.aspect}")
    private String a11yAspect;

    @Autowired
    private NodesApi nodesApi;

    @Autowired
    NodeUpdateService nodeUpdateService;

    @Autowired
    NodeStorageService nodeStorageService;

    @Autowired
    private A11yScore testScore;

    /**
     * Handles the node creation event triggered by the system. Checks for PDF renditions associated with documents
     * having the specified accessibility scoring aspect and initiates the document scoring process.
     *
     * @param repoEvent The event containing information about the created node.
     */
    @Override
    public void handleEvent(final RepoEvent<DataAttributes<Resource>> repoEvent) {
        NodeResource nodeResource = (NodeResource) repoEvent.getData().getResource();
        String uuid = nodeResource.getId();

        try {
            ResponseEntity<org.springframework.core.io.Resource> response = nodesApi.getNodeContent(uuid, false, null, null);
            org.springframework.core.io.Resource resource = response.getBody();

            if (resource == null || !resource.exists()) {
                LOG.warn("No content found for document with UUID {}", uuid);
                return;
            }

            A11yScore score = nodeStorageService.createA11yScoreFromNode(uuid);

            LOG.info("Score for document found in ContentA11yUpdatedHandler {}", uuid);
            LOG.info(score.toString());

        } catch (Exception e) {
            LOG.error("Failed to fetch content for document {}: {}", uuid, e.getMessage());
        }
    }

    /**
     * Specifies the event filter to determine which node update events this handler should process. The filter criteria
     * include the presence of the classified aspect, the "cm:content" node type, content changes, or the addition of the
     * classified aspect.
     *
     * @return An {@link EventFilter} representing the filter criteria for node update events.
     */
    @Override
    public EventFilter getEventFilter() {
        return NodeAspectFilter.of(a11yAspect)
                .and(NodeTypeFilter.of("cm:content"))
                .and(ContentChangedFilter.get())
                .or(AspectAddedFilter.of(a11yAspect));
    }
}