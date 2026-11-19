<?php
// Ephemeral test harness for unmodified upstream Mautic 7 Webhook Http Client.
// This file contains only synthetic data and local stub dependencies.
declare(strict_types=1);

namespace Psr\Http\Message {
    interface ResponseInterface {}
}
namespace Mautic\CoreBundle\Helper {
    final class CoreParametersHelper {
        public function get(string $name): mixed {
            return match ($name) {
                'site_url' => 'https://synthetic-mautic.example.invalid',
                'webhook_allowed_private_addresses' => [],
                default => throw new \RuntimeException('Unknown Mautic parameter'),
            };
        }
    }
    final class PrivateAddressChecker {
        public function setAllowedPrivateAddresses(array $addresses): void {
            if ($addresses !== []) {
                throw new \RuntimeException('Unexpected private-network bypass');
            }
        }
        public function isAllowedUrl(string $url): bool {
            return $url === 'https://synthetic-receiver.example.invalid/preview';
        }
    }
}
namespace Mautic\WebhookBundle\Exception {
    final class PrivateAddressException extends \RuntimeException {}
}
namespace GuzzleHttp\Psr7 {
    final class Request {
        public function __construct(
            public string $method,
            public string $url,
            public array $headers,
            public string $body,
        ) {}
    }
}
namespace PHPUnitContract {
    final class SyntheticResponse implements \Psr\Http\Message\ResponseInterface {}
}
namespace GuzzleHttp {
    class Client {
        public ?\GuzzleHttp\Psr7\Request $lastRequest = null;
        public function sendRequest(\GuzzleHttp\Psr7\Request $request): \Psr\Http\Message\ResponseInterface {
            $this->lastRequest = $request;
            return new \PHPUnitContract\SyntheticResponse();
        }
    }
}
namespace {
    if ($argc !== 2 || !is_file($argv[1])) {
        fwrite(STDERR, "Unmodified pinned upstream client source required\n");
        exit(2);
    }
    require_once $argv[1];
    $capture = new \GuzzleHttp\Client();
    $client = new \Mautic\WebhookBundle\Http\Client(
        new \Mautic\CoreBundle\Helper\CoreParametersHelper(),
        $capture,
        new \Mautic\CoreBundle\Helper\PrivateAddressChecker(),
    );
    $fixture = [
        'mautic.lead_channel_subscription_changed' => [[
            'contact' => [
                'id' => 42,
                'email' => 'synthetic-only@example.invalid',
            ],
            'channel' => 'email',
            'old_status' => 'contactable',
            'new_status' => 'unsubscribed',
            'timestamp' => '2026-11-19T10:00:00+00:00',
        ]],
    ];
    $response = $client->post(
        'https://synthetic-receiver.example.invalid/preview',
        $fixture,
        'only-synthetic-mautic-contract-secret-20261119',
    );
    $request = $capture->lastRequest;
    if ($request === null ||
        $request->method !== 'POST' ||
        $request->headers['Content-Type'] !== 'application/json' ||
        $request->headers['User-Agent'] !== 'Webhook' ||
        $request->headers['X-Origin-Base-URL'] !== 'https://synthetic-mautic.example.invalid' ||
        $request->body !== json_encode($fixture) ||
        !$response instanceof \PHPUnitContract\SyntheticResponse
    ) {
        fwrite(STDERR, "Mautic sender did not meet HTTP request contract\n");
        exit(3);
    }
    echo json_encode([
        'method' => $request->method,
        'url' => $request->url,
        'body_base64' => base64_encode($request->body),
        'webhook_signature' => $request->headers['Webhook-Signature'],
        'source_header_verified' => true,
        'raw_body_signed_by_upstream_php_client' => true,
    ], JSON_THROW_ON_ERROR);
}
