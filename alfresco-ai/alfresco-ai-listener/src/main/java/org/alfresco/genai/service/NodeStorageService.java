package org.alfresco.genai.service;

import org.alfresco.core.handler.NodesApi;
import org.alfresco.core.model.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Optional;

@Service
public class NodeStorageService {

    private static final Logger LOG = LoggerFactory.getLogger(NodeStorageService.class);
    private final NodesApi nodesApi;

    @Autowired
    public NodeStorageService(NodesApi nodesApi) {
        this.nodesApi = nodesApi;
    }

    public String ensureMyFilesReportFolder(String originalNodeId) {
        try {
            ResponseEntity<NodeAssociationPaging> parentList = nodesApi.listParents(
                    originalNodeId, "(isPrimary=true)", null, 0, 1, false, null
            );
            NodeAssociation parentEntry = parentList.getBody().getList().getEntries().get(0).getEntry();
            String parentFolderName = parentEntry.getName();

            String myFilesId = "-my-";
            String parentInMyFilesId = findOrCreateFolder(myFilesId, parentFolderName);

            ResponseEntity<NodeEntry> nodeResp = nodesApi.getNode(originalNodeId, null, null, null);
            String docName = nodeResp.getBody().getEntry().getName();
            String docBaseName = docName.replaceAll("\\.[^.]+$", "");

            return findOrCreateFolder(parentInMyFilesId, docBaseName);

        } catch (Exception e) {
            LOG.error("Failed to resolve report folder structure for node {}", originalNodeId, e);
            return "-my-";
        }
    }

    public String findOrCreateFolder(String parentFolderId, String folderName) {
        try {
            ResponseEntity<NodeChildAssociationPaging> children = nodesApi.listNodeChildren(
                    parentFolderId, null, null, null, null, null, null, false, null
            );

            for (NodeChildAssociationEntry child : children.getBody().getList().getEntries()) {
                if ("cm:folder".equals(child.getEntry().getNodeType()) &&
                        folderName.equals(child.getEntry().getName())) {
                    return child.getEntry().getId();
                }
            }

            NodeBodyCreate folderCreate = new NodeBodyCreate()
                    .name(folderName)
                    .nodeType("cm:folder");

            ResponseEntity<NodeEntry> created = nodesApi.createNode(
                    parentFolderId, folderCreate, false, null, null, null, null
            );
            return created.getBody().getEntry().getId();

        } catch (Exception e) {
            LOG.error("Failed to create or find folder '{}' under {}", folderName, parentFolderId, e);
            return parentFolderId;
        }
    }

    public String createOrUpdateJsonNode(String folderId, String filename, String jsonContent) {
        try {
            ResponseEntity<NodeChildAssociationPaging> children = nodesApi.listNodeChildren(
                folderId, null, null, null, null, null, null, false, null
            );

            for (NodeChildAssociationEntry child : children.getBody().getList().getEntries()) {
                if ("cm:content".equals(child.getEntry().getNodeType()) &&
                    filename.equals(child.getEntry().getName())) {

                    String existingNodeId = child.getEntry().getId();
                    nodesApi.updateNodeContent(
                        existingNodeId,
                        jsonContent.getBytes(StandardCharsets.UTF_8),
                        true,
                        "Updated A11y report",
                        filename,
                        null,
                        null
                    );
                    return existingNodeId;
                }
            }

            byte[] content = jsonContent.getBytes(StandardCharsets.UTF_8);

            if (!children.getBody().getList().getEntries().isEmpty()) {
                String existingNodeId = children.getBody().getList().getEntries().get(0).getEntry().getId();
                nodesApi.updateNodeContent(
                        existingNodeId, content, true, "Updated A11y report", filename, null, null
                );
                return existingNodeId;
            }

            NodeBodyCreate bodyCreate = new NodeBodyCreate()
                    .name(filename)
                    .nodeType("cm:content");

            ResponseEntity<NodeEntry> createdNode = nodesApi.createNode(
                    folderId, bodyCreate, false, false, null, null, null
            );

            String nodeId = createdNode.getBody().getEntry().getId();
            nodesApi.updateNodeContent(
                    nodeId, content, true, "Initial A11y report", filename, null, null
            );

            return nodeId;

        } catch (Exception e) {
            LOG.error("Failed to create or update JSON node in folder: {}", folderId, e);
            return null;
        }
    }  

    public Optional<String> getNodeTitle(String nodeId) {
        try {
            ResponseEntity<NodeEntry> response = nodesApi.getNode(nodeId, null, null, null);
            //return Optional.ofNullable((String) response.getBody().getEntry().getProperties().get("cm:title"));
            return Optional.ofNullable((String) response.getBody().getEntry().getName());
        } catch (Exception e) {
            LOG.warn("Could not get cm:title for node: {}", nodeId);
            return Optional.empty();
        }
    }

    // Not working yet: bidrectional links would be nice, both for user and programmatically
    public void linkDocumentToFolderAsReference(String documentNodeId, String folderNodeId) {
        try {
            ChildAssociationBody assocBody = new ChildAssociationBody()
                .childId(documentNodeId)
                .assocType("genai:hasReportFolder");

            nodesApi.createSecondaryChildAssociation(folderNodeId, assocBody, null);
        } catch (Exception e) {
            LOG.warn("Failed to link nodes {} → {} as attachment", folderNodeId, documentNodeId, e);
        }
    }
    
}
