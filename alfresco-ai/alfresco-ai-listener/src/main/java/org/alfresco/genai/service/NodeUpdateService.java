package org.alfresco.genai.service;

import org.alfresco.core.handler.NodesApi;
import org.alfresco.core.handler.TagsApi;
import org.alfresco.core.model.NodeBodyUpdate;
import org.alfresco.core.model.TagBody;
import org.alfresco.genai.model.A11yScore;
import org.alfresco.genai.model.Answer;
import org.alfresco.genai.model.Summary;
import org.alfresco.genai.model.Term;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.alfresco.genai.model.Description;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.core.io.InputStreamResource;

import java.io.FileInputStream;
import java.io.File;
import java.nio.file.Files;
import java.io.Serializable;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * The {@code NodeUpdateService} class is a Spring service responsible for updating document nodes in an Alfresco
 * Repository with summary information and answers. It utilizes the Alfresco Nodes API and Tags API for updating node
 * properties and creating tags associated with the document identified by its UUID.
 */
@Service
public class NodeUpdateService {

    private static final Logger LOG = LoggerFactory.getLogger(NodeStorageService.class);

    /**
     * Constant representing the property name for tags.
     */
    static final String TAG_PROPERTY = "TAG";

    /**
     * The property name for storing the document summary in the Alfresco repository obtained from configuration.
     */
    @Value("${content.service.summary.summary.property}")
    String summaryProperty;

    /**
     * The property name for storing the document tags in the Alfresco repository obtained from configuration.
     */
    @Value("${content.service.summary.tags.property}")
    String summaryTagsProperty;

    /**
     * The property name for storing the document model information in the Alfresco repository obtained from configuration.
     */
    @Value("${content.service.summary.model.property}")
    String summaryModelProperty;

    /**
     * The property name for storing the answer content in the Alfresco repository obtained from configuration.
     */
    @Value("${content.service.prompt.answer.property}")
    private String answerProperty;

    /**
     * The property name for storing the answer model information in the Alfresco repository obtained from configuration.
     */
    @Value("${content.service.prompt.model.property}")
    private String answerModelProperty;

    /**
     * Property that includes a list of terms for classification.
     */
    @Value("${content.service.classify.terms.property}")
    private String termsProperty;

    /**
     * The property name for storing the term content in the Alfresco repository obtained from configuration.
     */
    @Value("${content.service.classify.term.property}")
    private String termProperty;

    /**
     * The property name for storing the answer model information in the Alfresco repository obtained from configuration.
     */
    @Value("${content.service.classify.model.property}")
    private String termModelProperty;

    /**
     * Aspect name associated with picture description.
     */
    @Value("${content.service.description.aspect}")
    private String descriptionAspect;

    /**
     * The property name for storing the description content in the Alfresco repository obtained from configuration.
     */
    @Value("${content.service.description.description.property}")
    private String descriptionProperty;

    /**
     * The property name for storing the answer model information in the Alfresco repository obtained from configuration.
     */
    @Value("${content.service.description.model.property}")
    private String descriptionModelProperty;

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

    /**
     * Autowired instance of {@link NodesApi} for communication with the Alfresco Nodes API.
     */
    @Autowired
    NodesApi nodesApi;

    /**
     * Autowired instance of {@link TagsApi} for communication with the Alfresco Tags API.
     */
    @Autowired
    TagsApi tagsApi;

    /**
     * Updates the node properties and creates tags for the document identified by its UUID based on the provided
     * {@link Summary} object.
     *
     * @param uuid     The unique identifier of the document node.
     * @param summary  The {@link Summary} object containing summary, tags, and model information.
     */
    public void updateNodeSummary(String uuid, Summary summary) {

        Map<String, Object> properties = new HashMap<>();
        properties.put(summaryProperty, summary.getSummary());
        if (!summaryModelProperty.equals(TAG_PROPERTY)) {
            properties.put(summaryModelProperty, summary.getModel());
        }
        if (!summaryTagsProperty.equals(TAG_PROPERTY)) {
            properties.put(summaryTagsProperty, summary.getTags());
        }
        nodesApi.updateNode(uuid,
                new NodeBodyUpdate().properties(properties),
                null, null);

        if (summaryModelProperty.equals(TAG_PROPERTY)) {
            tagsApi.createTagForNode(uuid, new TagBody().tag(summary.getModel()), null);
        }

        if (summaryTagsProperty.equals(TAG_PROPERTY)) {
            summary.getTags().forEach(tag -> {
                tagsApi.createTagForNode(uuid, new TagBody().tag(tag.replace('.', ' ').trim()), null);
            });
        }

    }

    /**
     * Updates the node properties with answer content and model information for the document identified by its UUID based
     * on the provided {@link Answer} object.
     *
     * @param uuid    The unique identifier of the document node.
     * @param answer  The {@link Answer} object containing the answer content and model information.
     */
    public void updateNodeAnswer(String uuid, Answer answer) {
        nodesApi.updateNode(uuid,
                new NodeBodyUpdate()
                        .properties(Map.of(
                                answerProperty, answer.getAnswer(),
                                answerModelProperty, answer.getModel())),
                null, null);
    }

    /**
     * Updates the node properties with term content and model information for the document identified by its UUID based
     * on the provided {@link Term} object.
     *
     * @param uuid  The unique identifier of the document node.
     * @param term  The {@link Term} object containing the answer content and model information.
     */
    public void updateNodeTerm(String uuid, Term term) {
        nodesApi.updateNode(uuid,
                new NodeBodyUpdate()
                        .properties(Map.of(
                                termProperty, term.getTerm(),
                                termModelProperty, term.getModel())),
                null, null);
    }

    /**
     * Updates the node properties with scoring content and model information for the document identified by its UUID based
     * on the provided {@link A11yScore} object.
     *
     * @param uuid  The unique identifier of the document node.
     * @param score  The {@link A11yScore} object containing the scoring info.
     */
    public void updateNodeA11yScore(String uuid, A11yScore score) {
        Map<String, Object> properties = new HashMap<>();
    
        LOG.info("Updating node {} with accessibility score data", uuid);
    
        // Log full raw report for reference
        LOG.debug("Full A11yScore Report:\nSummary: {}\nRules: {}",
                score.getSummaryDescription(),
                score.getRuleResults());
    
        // Base score fields
        logAndPut(properties, accessibilityScoreProperty, score.getScore());
        logAndPut(properties, accessibilityModelScoreProperty, score.getModel());
    
        // Summary fields
        logAndPut(properties, accessibilitySummaryDescriptionProperty, score.getSummaryDescription());
        logAndPut(properties, accessibilitySummaryNeedsManualCheckProperty, score.getSummaryNeedsManualCheck());
        logAndPut(properties, accessibilitySummaryPassedManuallyProperty, score.getSummaryPassedManually());
        logAndPut(properties, accessibilitySummaryFailedManuallyProperty, score.getSummaryFailedManually());
        logAndPut(properties, accessibilitySummarySkippedProperty, score.getSummarySkipped());
        logAndPut(properties, accessibilitySummaryPassedProperty, score.getSummaryPassed());
        logAndPut(properties, accessibilitySummaryFailedProperty, score.getSummaryFailed());
    
        // Rule fields
        Map<String, String> rules = score.getRuleResults();
        putRule(properties, ruleAccessibilityPermissionFlagProperty, rules, "AccessibilityPermissionFlag");
        putRule(properties, ruleImageOnlyPDFProperty, rules, "ImageOnlyPDF");
        putRule(properties, ruleTaggedPDFProperty, rules, "TaggedPDF");
        putRule(properties, ruleLogicalReadingOrderProperty, rules, "LogicalReadingOrder");
        putRule(properties, rulePrimaryLanguageProperty, rules, "PrimaryLanguage");
        putRule(properties, ruleTitleProperty, rules, "Title");
        putRule(properties, ruleBookmarksProperty, rules, "Bookmarks");
        putRule(properties, ruleColorContrastProperty, rules, "ColorContrast");
        putRule(properties, ruleTaggedContentProperty, rules, "TaggedContent");
        putRule(properties, ruleTaggedAnnotationsProperty, rules, "TaggedAnnotations");
        putRule(properties, ruleTabOrderProperty, rules, "TabOrder");
        putRule(properties, ruleCharacterEncodingProperty, rules, "CharacterEncoding");
        putRule(properties, ruleTaggedMultimediaProperty, rules, "TaggedMultimedia");
        putRule(properties, ruleScreenFlickerProperty, rules, "ScreenFlicker");
        putRule(properties, ruleScriptsProperty, rules, "Scripts");
        putRule(properties, ruleTimedResponsesProperty, rules, "TimedResponses");
        putRule(properties, ruleNavigationLinksProperty, rules, "NavigationLinks");
        putRule(properties, ruleTaggedFormFieldsProperty, rules, "TaggedFormFields");
        putRule(properties, ruleFieldDescriptionsProperty, rules, "FieldDescriptions");
        putRule(properties, ruleFiguresAlternateTextProperty, rules, "FiguresAlternateText");
        putRule(properties, ruleNestedAlternateTextProperty, rules, "NestedAlternateText");
        putRule(properties, ruleAssociatedWithContentProperty, rules, "AssociatedWithContent");
        putRule(properties, ruleHidesAnnotationProperty, rules, "HidesAnnotation");
        putRule(properties, ruleOtherElementsAlternateTextProperty, rules, "OtherElementsAlternateText");
        putRule(properties, ruleRowsProperty, rules, "Rows");
        putRule(properties, ruleTHAndTDProperty, rules, "THAndTD");
        putRule(properties, ruleHeadersProperty, rules, "Headers");
        putRule(properties, ruleRegularityProperty, rules, "Regularity");
        putRule(properties, ruleSummaryProperty, rules, "Summary");
        putRule(properties, ruleListItemsProperty, rules, "ListItems");
        putRule(properties, ruleLblAndLBodyProperty, rules, "LblAndLBody");
        putRule(properties, ruleAppropriateNestingProperty, rules, "AppropriateNesting");
    
        // Log final property map
        LOG.debug("📦 Final properties to update on node {}: {}", uuid, properties);
    
        // Update Alfresco node
        nodesApi.updateNode(uuid, new NodeBodyUpdate().properties(properties), null, null);
    }
    
    // Helper to log and put a property
    private void logAndPut(Map<String, Object> map, String key, Object value) {
        LOG.debug("Setting property {} = {}", key, value);
        map.put(key, value);
    }
    
    // Helper to handle rules from map
    private void putRule(Map<String, Object> map, String propertyKey, Map<String, String> rules, String ruleKey) {
        String value = rules.get(ruleKey);
        if (value != null) {
            logAndPut(map, propertyKey, value);
        } else {
            LOG.warn("Rule '{}' not found in A11yScore.getRuleResults()", ruleKey);
        }
    }

    public void storeAccessibleVersion(String uuid, File accessibleVersion, boolean isMajorVersion) {
        try {
            byte[] content = Files.readAllBytes(accessibleVersion.toPath());
    
            nodesApi.updateNodeContent(
                    uuid,
                    content,
                    isMajorVersion,
                    accessibleVersion.getName(),
                    null,                             // contentType (null = auto-detect)
                    null,                             // include
                    null                              // fields
            );
    
            LOG.info("Stored accessible PDF version as new content for node {}", uuid);
        } catch (Exception e) {
            LOG.error("Failed to store accessible version for node {}: {}", uuid, e.getMessage(), e);
        }
    }

    /**
     * Gets the list of terms stored in the primary parent of the document uuid
     *
     * @param uuid  The unique identifier of the document node.
     */
    public String getTermList(String uuid) {
        String primaryParentId =
                nodesApi.listParents(uuid, "(isPrimary=true)", null, 0, 1, false, null)
                        .getBody()
                        .getList()
                        .getEntries()
                        .get(0)
                        .getEntry()
                        .getId();
        Map<String, Serializable> properties = (Map<String, Serializable>)
                nodesApi.getNode(primaryParentId, null, null, null)
                .getBody()
                .getEntry().getProperties();
        return properties.get(termsProperty).toString().replace("[", "").replace("]", "");
    }

    /**
     * Updates the node properties with description and model information for the document identified by its UUID based
     * on the provided {@link Description} object.
     *
     * @param uuid         The unique identifier of the picture node.
     * @param description  The {@link Description} object containing the answer content and model information.
     */
    public void updateNodeDescription(String uuid, Description description) {

        List<String> aspectNames =
                nodesApi.getNode(uuid, null, null, null).getBody().getEntry().getAspectNames();
        if (!aspectNames.contains(descriptionAspect)) {
            aspectNames.add(descriptionAspect);
        }

        nodesApi.updateNode(uuid,
                new NodeBodyUpdate()
                        .properties(Map.of(
                                descriptionProperty, description.getDescription(),
                                descriptionModelProperty, description.getModel()))
                        .aspectNames(aspectNames),
                null, null);
    }

}

