package org.alfresco.genai.service;

import org.alfresco.core.handler.NodesApi;
import org.alfresco.core.model.*;
import org.alfresco.genai.model.A11yScore;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;

import java.io.Serializable;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Service
public class NodeStorageService {

    private static final Logger LOG = LoggerFactory.getLogger(NodeStorageService.class);
    private final NodesApi nodesApi;

    // --- Old A11y Summary Fields ---
    @Value("${content.service.a11y.score.property}")
    private String accessibilityScoreProperty;

    @Value("${content.service.a11y.score.model.property}")
    private String accessibilityModelScoreProperty;

    // --- A11y Summary Fields ---
    @Value("${content.service.a11y.summary.description.property}")
    private String accessibilitySummaryDescriptionProperty;

    @Value("${content.service.a11y.summary.needsManualCheck.property}")
    private String accessibilitySummaryNeedsManualCheckProperty;

    @Value("${content.service.a11y.summary.passedManually.property}")
    private String accessibilitySummaryPassedManuallyProperty;

    @Value("${content.service.a11y.summary.failedManually.property}")
    private String accessibilitySummaryFailedManuallyProperty;

    @Value("${content.service.a11y.summary.skipped.property}")
    private String accessibilitySummarySkippedProperty;

    @Value("${content.service.a11y.summary.passed.property}")
    private String accessibilitySummaryPassedProperty;

    @Value("${content.service.a11y.summary.failed.property}")
    private String accessibilitySummaryFailedProperty;

    // --- A11y Rule Results ---
    @Value("${content.service.a11y.rule.accessibilityPermissionFlag.property}")
    private String ruleAccessibilityPermissionFlagProperty;

    @Value("${content.service.a11y.rule.imageOnlyPDF.property}")
    private String ruleImageOnlyPDFProperty;

    @Value("${content.service.a11y.rule.taggedPDF.property}")
    private String ruleTaggedPDFProperty;

    @Value("${content.service.a11y.rule.logicalReadingOrder.property}")
    private String ruleLogicalReadingOrderProperty;

    @Value("${content.service.a11y.rule.primaryLanguage.property}")
    private String rulePrimaryLanguageProperty;

    @Value("${content.service.a11y.rule.title.property}")
    private String ruleTitleProperty;

    @Value("${content.service.a11y.rule.bookmarks.property}")
    private String ruleBookmarksProperty;

    @Value("${content.service.a11y.rule.colorContrast.property}")
    private String ruleColorContrastProperty;

    @Value("${content.service.a11y.rule.taggedContent.property}")
    private String ruleTaggedContentProperty;

    @Value("${content.service.a11y.rule.taggedAnnotations.property}")
    private String ruleTaggedAnnotationsProperty;

    @Value("${content.service.a11y.rule.tabOrder.property}")
    private String ruleTabOrderProperty;

    @Value("${content.service.a11y.rule.characterEncoding.property}")
    private String ruleCharacterEncodingProperty;

    @Value("${content.service.a11y.rule.taggedMultimedia.property}")
    private String ruleTaggedMultimediaProperty;

    @Value("${content.service.a11y.rule.screenFlicker.property}")
    private String ruleScreenFlickerProperty;

    @Value("${content.service.a11y.rule.scripts.property}")
    private String ruleScriptsProperty;

    @Value("${content.service.a11y.rule.timedResponses.property}")
    private String ruleTimedResponsesProperty;

    @Value("${content.service.a11y.rule.navigationLinks.property}")
    private String ruleNavigationLinksProperty;

    @Value("${content.service.a11y.rule.taggedFormFields.property}")
    private String ruleTaggedFormFieldsProperty;

    @Value("${content.service.a11y.rule.fieldDescriptions.property}")
    private String ruleFieldDescriptionsProperty;

    @Value("${content.service.a11y.rule.figuresAlternateText.property}")
    private String ruleFiguresAlternateTextProperty;

    @Value("${content.service.a11y.rule.nestedAlternateText.property}")
    private String ruleNestedAlternateTextProperty;

    @Value("${content.service.a11y.rule.associatedWithContent.property}")
    private String ruleAssociatedWithContentProperty;

    @Value("${content.service.a11y.rule.hidesAnnotation.property}")
    private String ruleHidesAnnotationProperty;

    @Value("${content.service.a11y.rule.otherElementsAlternateText.property}")
    private String ruleOtherElementsAlternateTextProperty;

    @Value("${content.service.a11y.rule.rows.property}")
    private String ruleRowsProperty;

    @Value("${content.service.a11y.rule.thAndTd.property}")
    private String ruleTHAndTDProperty;

    @Value("${content.service.a11y.rule.headers.property}")
    private String ruleHeadersProperty;

    @Value("${content.service.a11y.rule.regularity.property}")
    private String ruleRegularityProperty;

    @Value("${content.service.a11y.rule.summary.property}")
    private String ruleSummaryProperty;

    @Value("${content.service.a11y.rule.listItems.property}")
    private String ruleListItemsProperty;

    @Value("${content.service.a11y.rule.lblAndLBody.property}")
    private String ruleLblAndLBodyProperty;

    @Value("${content.service.a11y.rule.appropriateNesting.property}")
    private String ruleAppropriateNestingProperty;

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

    public A11yScore createA11yScoreFromNode(String uuid) {
        Map<String, Serializable> props = (Map<String, Serializable>)
                nodesApi.getNode(uuid, null, null, null)
                        .getBody()
                        .getEntry()
                        .getProperties();

        A11yScore score = new A11yScore();

        // Score & model
        score.setScore((String) props.getOrDefault(accessibilityScoreProperty, ""));
        score.setModel((String) props.getOrDefault(accessibilityModelScoreProperty, ""));

        // Summary
        score.setSummaryDescription((String) props.getOrDefault(accessibilitySummaryDescriptionProperty, ""));
        score.setSummaryNeedsManualCheck(getInt(props.get(accessibilitySummaryNeedsManualCheckProperty)));
        score.setSummaryPassedManually(getInt(props.get(accessibilitySummaryPassedManuallyProperty)));
        score.setSummaryFailedManually(getInt(props.get(accessibilitySummaryFailedManuallyProperty)));
        score.setSummarySkipped(getInt(props.get(accessibilitySummarySkippedProperty)));
        score.setSummaryPassed(getInt(props.get(accessibilitySummaryPassedProperty)));
        score.setSummaryFailed(getInt(props.get(accessibilitySummaryFailedProperty)));

        // Rules
        Map<String, String> ruleMap = new HashMap<>();
        putRule(ruleMap, "AccessibilityPermissionFlag", props.get(ruleAccessibilityPermissionFlagProperty));
        putRule(ruleMap, "ImageOnlyPDF", props.get(ruleImageOnlyPDFProperty));
        putRule(ruleMap, "TaggedPDF", props.get(ruleTaggedPDFProperty));
        putRule(ruleMap, "LogicalReadingOrder", props.get(ruleLogicalReadingOrderProperty));
        putRule(ruleMap, "PrimaryLanguage", props.get(rulePrimaryLanguageProperty));
        putRule(ruleMap, "Title", props.get(ruleTitleProperty));
        putRule(ruleMap, "Bookmarks", props.get(ruleBookmarksProperty));
        putRule(ruleMap, "ColorContrast", props.get(ruleColorContrastProperty));
        putRule(ruleMap, "TaggedContent", props.get(ruleTaggedContentProperty));
        putRule(ruleMap, "TaggedAnnotations", props.get(ruleTaggedAnnotationsProperty));
        putRule(ruleMap, "TabOrder", props.get(ruleTabOrderProperty));
        putRule(ruleMap, "CharacterEncoding", props.get(ruleCharacterEncodingProperty));
        putRule(ruleMap, "TaggedMultimedia", props.get(ruleTaggedMultimediaProperty));
        putRule(ruleMap, "ScreenFlicker", props.get(ruleScreenFlickerProperty));
        putRule(ruleMap, "Scripts", props.get(ruleScriptsProperty));
        putRule(ruleMap, "TimedResponses", props.get(ruleTimedResponsesProperty));
        putRule(ruleMap, "NavigationLinks", props.get(ruleNavigationLinksProperty));
        putRule(ruleMap, "TaggedFormFields", props.get(ruleTaggedFormFieldsProperty));
        putRule(ruleMap, "FieldDescriptions", props.get(ruleFieldDescriptionsProperty));
        putRule(ruleMap, "FiguresAlternateText", props.get(ruleFiguresAlternateTextProperty));
        putRule(ruleMap, "NestedAlternateText", props.get(ruleNestedAlternateTextProperty));
        putRule(ruleMap, "AssociatedWithContent", props.get(ruleAssociatedWithContentProperty));
        putRule(ruleMap, "HidesAnnotation", props.get(ruleHidesAnnotationProperty));
        putRule(ruleMap, "OtherElementsAlternateText", props.get(ruleOtherElementsAlternateTextProperty));
        putRule(ruleMap, "Rows", props.get(ruleRowsProperty));
        putRule(ruleMap, "THAndTD", props.get(ruleTHAndTDProperty));
        putRule(ruleMap, "Headers", props.get(ruleHeadersProperty));
        putRule(ruleMap, "Regularity", props.get(ruleRegularityProperty));
        putRule(ruleMap, "Summary", props.get(ruleSummaryProperty));
        putRule(ruleMap, "ListItems", props.get(ruleListItemsProperty));
        putRule(ruleMap, "LblAndLBody", props.get(ruleLblAndLBodyProperty));
        putRule(ruleMap, "AppropriateNesting", props.get(ruleAppropriateNestingProperty));

        score.setRuleResults(ruleMap);

        return score;
    }

    private int getInt(Object value) {
        if (value instanceof Integer) return (int) value;
        if (value instanceof String) return Integer.parseInt((String) value);
        return 0;
    }

    private void putRule(Map<String, String> map, String ruleKey, Object value) {
        if (value != null) {
            map.put(ruleKey, value.toString());
        }
    }

}
