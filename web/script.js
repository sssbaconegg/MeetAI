// FastAPI 서버 주소 - 필요하면 이 값만 바꾸면 됩니다.
const API_BASE_URL = "http://127.0.0.1:8000";
const POLL_INTERVAL_MS = 3000;

$(function () {
  const $memo = $("#memo");
  const $audioFile = $("#audio-file");
  const $fileName = $("#file-name");
  const $generateBtn = $("#generate-btn");
  const $errorMessage = $("#error-message");
  const $loading = $("#loading");
  const $loadingText = $("#loading-text");
  const $result = $("#result");

  let pollTimer = null;

  $audioFile.on("change", function () {
    const file = this.files[0];
    $fileName.text(file ? file.name : "");
  });

  $generateBtn.on("click", function () {
    const file = $audioFile[0].files[0];

    hideError();

    if (!file) {
      showError("녹음 파일(mp3 또는 wav)을 선택해주세요.");
      return;
    }

    const formData = new FormData();
    formData.append("audio_file", file);
    if ($memo.val().trim()) {
      formData.append("memo", $memo.val().trim());
    }

    setBusy(true);
    $result.prop("hidden", true);

    $.ajax({
      url: `${API_BASE_URL}/upload-audio`,
      method: "POST",
      data: formData,
      processData: false,
      contentType: false,
    })
      .done(function (job) {
        pollJob(job.job_id, Date.now());
      })
      .fail(function (xhr) {
        setBusy(false);
        showError(describeAjaxError(xhr, "요청 전송에 실패했습니다."));
      });
  });

  function pollJob(jobId, startedAt) {
    const elapsedSec = Math.floor((Date.now() - startedAt) / 1000);
    $loadingText.text(`회의록을 생성하고 있습니다... (${elapsedSec}초 경과)`);

    $.ajax({
      url: `${API_BASE_URL}/jobs/${jobId}`,
      method: "GET",
    })
      .done(function (job) {
        if (job.status === "processing") {
          pollTimer = setTimeout(() => pollJob(jobId, startedAt), POLL_INTERVAL_MS);
          return;
        }

        setBusy(false);

        if (job.status === "failed") {
          showError(`회의록 생성에 실패했습니다: ${job.error || "알 수 없는 오류"}`);
          return;
        }

        renderResult(job);
      })
      .fail(function (xhr) {
        setBusy(false);
        showError(describeAjaxError(xhr, "상태 조회에 실패했습니다."));
      });
  }

  function renderResult(job) {
    const summary = job.summary || {};

    $("#result-topic").text(summary["회의 주제"] || "(회의 주제 없음)");

    const datetime = summary["일시"];
    $("#result-datetime").text(datetime ? `🗓️ ${datetime}` : "").toggle(Boolean(datetime));

    renderBulletList("#result-highlights", summary["핵심내용"]);
    renderBulletList("#result-decisions", summary["결정사항"]);

    const $taskBody = $("#result-tasks tbody").empty();
    const tasks = summary["담당업무"] || [];
    if (tasks.length === 0) {
      $taskBody.append('<tr><td colspan="2" class="empty-cell">없음</td></tr>');
    } else {
      tasks.forEach(function (task) {
        const $row = $("<tr>");
        $row.append($("<td>").text(task["담당자"] || "-"));
        $row.append($("<td>").text(task["업무"] || "-"));
        $taskBody.append($row);
      });
    }

    $("#result-next-meeting").text(summary["다음회의"] || "미정");
    $("#result-transcript").text(job.transcript || "전사 결과가 없습니다.");

    $result.prop("hidden", false);
  }

  function renderBulletList(selector, items) {
    const $list = $(selector).empty();
    if (!items || items.length === 0) {
      $list.addClass("is-empty");
      return;
    }
    $list.removeClass("is-empty");
    items.forEach(function (item) {
      $list.append($("<li>").text(item));
    });
  }

  function setBusy(isBusy) {
    $generateBtn.prop("disabled", isBusy);
    $loading.prop("hidden", !isBusy);
    if (!isBusy && pollTimer) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
  }

  function showError(message) {
    $errorMessage.text(message).prop("hidden", false);
  }

  function hideError() {
    $errorMessage.text("").prop("hidden", true);
  }

  function describeAjaxError(xhr, fallback) {
    if (xhr.responseJSON && xhr.responseJSON.detail) {
      return xhr.responseJSON.detail;
    }
    if (xhr.status === 0) {
      return `${fallback} (서버에 연결할 수 없습니다. API 서버가 실행 중인지 확인하세요: ${API_BASE_URL})`;
    }
    return `${fallback} (HTTP ${xhr.status})`;
  }
});
