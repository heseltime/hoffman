package org.alfresco.genai.event;
import java.io.IOException;
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
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * The {@code ContentClassifyCreatedHandler} class is a Spring component that extends the {@link AbstractContentTypeHandler}
 * and implements the {@link OnNodeCreatedEventHandler} interface. It is responsible for handling events triggered upon
 * the creation of nodes with a specified content type, focusing on nodes with the "cm:content" type and a specific classified aspect.
 *
 * <p>This handler provides a concise event filter definition using a combination of filters to identify relevant node
 * creation events. The filter criteria include the presence of the classified aspect and the "cm:content" node type.
 */
@Component
public class ContentA11yCreatedHandler extends AbstractContentTypeHandler implements OnNodeCreatedEventHandler {

    /**
     * Logger for logging information and error messages.
     */
    private static final Logger LOG = LoggerFactory.getLogger(RenditionClassifyCreatedHandler.class);

    /**
     * Aspect name associated with document accessibility scoring.
     */
    @Value("${content.service.a11y.aspect}")
    private String a11yAspect;

    /**
     * Autowired instance of {@link NodesApi} for working with Alfresco nodes.
     */
    @Autowired
    NodesApi nodesApi;

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

        // TODO: how to get document

        LOG.info("A11y (Accessibility)-scoring document {}", uuid);
        A11yScore testScore = new A11yScore(); // TODO: pass document here
        testScore.score("test score"); // TODO: remove
        nodeUpdateService.updateNodeA11yScore(
                uuid,
                testScore); // genAiClient.getTerm(renditionService.getRenditionContent(uuid), nodeUpdateService.getTermList(uuid))
        LOG.info("Document {} has been created with a11y-score and model", uuid);
    }

    /**
     * Specifies the event filter to determine which node creation events this handler should process. The filter criteria
     * include the presence of the classified aspect and the "cm:content" node type.
     *
     * @return An {@link EventFilter} representing the filter criteria for node creation events.
     */
    @Override
    public EventFilter getEventFilter() {
        return NodeAspectFilter.of(a11yAspect)
                .and(NodeTypeFilter.of("cm:content"));
    }
}