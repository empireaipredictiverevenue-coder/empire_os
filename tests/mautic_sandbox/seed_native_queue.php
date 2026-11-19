<?php
declare(strict_types=1);

// CI-ONLY native Mautic 7 queue seeder. Never use with real users or a
// production database; only permit the disposable, synthetic contract DB.
if (
    getenv('MAUTIC_CONTRACT_ONLY') !== '1'
    || getenv('MAUTIC_DB_DATABASE') !== 'mautic_contract_test'
    || strlen((string) getenv('MAUTIC_CONTRACT_WEBHOOK_SECRET')) < 32
) {
    fwrite(STDERR, "REFUSE_NON_SYNTHETIC_MAUTIC_QUEUE_SEED\n");
    exit(3);
}

require '/var/www/html/vendor/autoload.php';

use Mautic\WebhookBundle\Entity\Webhook;
use Mautic\WebhookBundle\Entity\WebhookQueue;

$kernel = new AppKernel('prod', false);
$kernel->boot();

$container = $kernel->getContainer();
$em = $container->get('doctrine')->getManager();

$webhook = new Webhook();
$webhook->setName('CI Synthetic Mautic Queue Proof');
$webhook->setDescription('Isolated webhook test, no production sender');
$webhook->setWebhookUrl(
    'http://receiver:8081/v1/revenue-crm/integrations/mautic/ci/events/preview'
);
$webhook->setSecret((string) getenv('MAUTIC_CONTRACT_WEBHOOK_SECRET'));
$webhook->setIsPublished(true);
// Native Mautic normally stamps these fields in WebhookModel::saveEntity.
// This isolated fixture persists through Doctrine directly; preserve the
// normal "recently modified" lifecycle so an intentional first HTTP 503
// cannot misclassify a freshly created synthetic webhook as abandoned.
$webhook->setDateAdded(new DateTime());
$webhook->setDateModified(new DateTime());
$webhook->addTrigger('mautic.lead_channel_subscription_changed');
$em->persist($webhook);
$em->flush();

$event = $webhook->getEvents()->first();
if (!$event instanceof Mautic\WebhookBundle\Entity\Event) {
    throw new RuntimeException('Mautic webhook event not persisted');
}

$payload = [
    'contact' => [
        'id' => 42,
        'email' => 'synthetic-mautic-contact@example.invalid',
    ],
    'channel' => 'email',
    'old_status' => 'contactable',
    'new_status' => 'unsubscribed',
];

$queue = new WebhookQueue();
$queue->setWebhook($webhook);
$queue->setEvent($event);
$queue->setDateAdded(new DateTime());
$queue->setPayload(json_encode($payload, JSON_THROW_ON_ERROR));
$em->persist($queue);
$em->flush();

if (!$queue->getId() || !$webhook->getId()) {
    throw new RuntimeException('Mautic native queue database insert failed');
}
echo 'CI_WEBHOOK_ID='.$webhook->getId()."\n";
echo 'CI_QUEUE_CREATED_BY_INSTALLED_MAUTIC_7=yes'."\n";

$kernel->shutdown();
